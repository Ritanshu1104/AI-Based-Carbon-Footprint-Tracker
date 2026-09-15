"""Consent-gated route-distance evidence providers."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class RouteEvidenceService:
    GOOGLE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(self, google_key=None, osrm_url=None, timeout=12):
        self.google_key = google_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        self.osrm_url = (osrm_url or os.environ.get(
            "OSRM_BASE_URL", "https://router.project-osrm.org"
        )).rstrip("/")
        self.timeout = timeout

    @property
    def capability(self):
        return {
            "google_routes": bool(self.google_key),
            "osrm_coordinates": bool(self.osrm_url),
            "privacy_notice": (
                "Route requests transmit the supplied locations to the selected provider. "
                "The endpoint refuses requests unless explicit consent is included."
            ),
        }

    def route(self, payload):
        if payload.get("consent_external_processing") is not True:
            raise ValueError("Explicit consent is required before locations are sent to a route provider")
        provider = payload.get("provider", "google" if self.google_key else "osrm")
        if provider == "google":
            return self._google(payload)
        if provider == "osrm":
            return self._osrm(payload)
        raise ValueError("Provider must be google or osrm")

    def _google(self, payload):
        if not self.google_key:
            raise ValueError("Google Routes is unavailable; configure GOOGLE_MAPS_API_KEY")
        body = {
            "origin": self._google_location(payload.get("origin")),
            "destination": self._google_location(payload.get("destination")),
            "travelMode": self._google_mode(payload.get("mode", "driving")),
            "routingPreference": "TRAFFIC_UNAWARE",
            "computeAlternativeRoutes": False,
            "languageCode": "en-US",
            "units": "METRIC",
        }
        request = urllib.request.Request(
            self.GOOGLE_URL, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={
                "Content-Type": "application/json", "X-Goog-Api-Key": self.google_key,
                "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.routeLabels",
            },
        )
        data = self._json(request)
        routes = data.get("routes", [])
        if not routes:
            raise ValueError("Google Routes returned no route")
        route = routes[0]
        return self._result(
            "Google Routes API", route["distanceMeters"], route.get("duration"),
            "https://developers.google.com/maps/documentation/routes",
        )

    def _osrm(self, payload):
        origin = self._coordinates(payload.get("origin"), "origin")
        destination = self._coordinates(payload.get("destination"), "destination")
        profile = {"driving": "driving", "cycling": "cycling", "walking": "walking"}.get(
            payload.get("mode", "driving"), "driving"
        )
        coordinate_text = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = (f"{self.osrm_url}/route/v1/{profile}/{coordinate_text}"
               "?overview=false&steps=false&alternatives=false")
        request = urllib.request.Request(url, headers={
            "User-Agent": "CarbonEvidenceLab/1.0 (local research prototype)"
        })
        data = self._json(request)
        routes = data.get("routes", [])
        if data.get("code") != "Ok" or not routes:
            raise ValueError(data.get("message") or "OSRM returned no route")
        route = routes[0]
        return self._result(
            "Open Source Routing Machine", route["distance"], route.get("duration"),
            "https://project-osrm.org/docs/v5.24.0/api/#route-service",
        )

    def _json(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            raise ValueError(f"Route provider rejected the request ({error.code}): {detail}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ValueError(f"Route provider is unavailable: {error}") from error

    @staticmethod
    def _coordinates(value, field):
        if isinstance(value, dict):
            latitude, longitude = value.get("latitude"), value.get("longitude")
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            latitude, longitude = value
        else:
            raise ValueError(f"{field} must contain latitude and longitude for OSRM")
        latitude, longitude = float(latitude), float(longitude)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"{field} coordinates are outside valid ranges")
        return latitude, longitude

    @staticmethod
    def _google_location(value):
        if isinstance(value, str) and value.strip():
            return {"address": value.strip()}
        latitude, longitude = RouteEvidenceService._coordinates(value, "location")
        return {"location": {"latLng": {"latitude": latitude, "longitude": longitude}}}

    @staticmethod
    def _google_mode(mode):
        return {"driving": "DRIVE", "cycling": "BICYCLE", "walking": "WALK",
                "transit": "TRANSIT", "two_wheeler": "TWO_WHEELER"}.get(mode, "DRIVE")

    @staticmethod
    def _result(provider, distance_meters, duration, source_url):
        return {
            "distance_km": round(float(distance_meters) / 1000, 3),
            "duration": duration, "provider": provider,
            "evidence_type": "externally-verified-route", "source_url": source_url,
        }
