"""
maps_service.py

Resolves place names typed by the user (however spelled) into
coordinates, and coordinates into a real route distance -- entirely
via live geocoding/routing services. There is NO hardcoded list of
cities/places anywhere in this file; every lookup is a live API call.

Geocoding chain (each only runs if the previous one fails/returns nothing):
  1. Nominatim (OpenStreetMap) -- free, no key.
  2. Photon (Komoot, also OSM-based) -- free, no key, independent service
     and index from Nominatim, so it often succeeds where Nominatim
     doesn't (typos, informal names) and vice versa.
  3. Google Geocoding API -- only used if GOOGLE_MAPS_API_KEY is set.
     Most accurate/typo-tolerant, but needs billing enabled.

Routing chain for the distance between two resolved points:
  1. Google Distance Matrix (if GOOGLE_MAPS_API_KEY is set) -- real road
     route distance.
  2. OSRM public demo server -- real road route distance, free, but
     rate-limited and not meant for production traffic.
  3. Haversine straight-line distance -- last-resort estimate if both
     routing services are unreachable.

Every function returns the *real reason* for a failure (timeout, no
result, HTTP error, etc.) instead of swallowing it, so the UI can show
the user something more useful than "not found".
"""

import os
import math
from typing import Optional, Tuple

import requests

GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

_HEADERS = {
    "User-Agent": "carbon-footprint-tracker/1.0 (student project; contact: set-your-email-here)",
    "Accept-Language": "en",
}

_TIMEOUT = 8  # seconds


def _get_json(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _geocode_nominatim(place: str):
    try:
        data = _get_json(
            "https://nominatim.openstreetmap.org/search",
            {"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 0},
        )
        if data:
            return (float(data[0]["lat"]), float(data[0]["lon"])), None
        return None, "Nominatim: no match"
    except requests.exceptions.RequestException as e:
        return None, f"Nominatim error: {e}"
    except Exception as e:
        return None, f"Nominatim parse error: {e}"


def _geocode_photon(place: str):
    try:
        data = _get_json("https://photon.komoot.io/api/", {"q": place, "limit": 1})
        feats = data.get("features") or []
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            return (lat, lon), None
        return None, "Photon: no match"
    except requests.exceptions.RequestException as e:
        return None, f"Photon error: {e}"
    except Exception as e:
        return None, f"Photon parse error: {e}"


def _geocode_google(place: str):
    try:
        data = _get_json(
            "https://maps.googleapis.com/maps/api/geocode/json",
            {"address": place, "key": GOOGLE_API_KEY},
        )
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            return (loc["lat"], loc["lng"]), None
        return None, f"Google geocode: {data.get('status', 'no result')}"
    except requests.exceptions.RequestException as e:
        return None, f"Google geocode error: {e}"


def geocode(place: str):
    """
    Returns ((lat, lon), errors). Coordinates are None only if every
    provider failed; `errors` always lists what each provider said,
    for debugging.
    """
    errors = []
    providers = ([_geocode_google] if GOOGLE_API_KEY else []) + [_geocode_nominatim, _geocode_photon]
    for fn in providers:
        coords, err = fn(place)
        if coords:
            return coords, errors
        errors.append(err)
    return None, errors


def haversine_km(a, b) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _route_google(o, d):
    try:
        data = _get_json(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            {"origins": f"{o[0]},{o[1]}", "destinations": f"{d[0]},{d[1]}", "key": GOOGLE_API_KEY},
        )
        meters = data["rows"][0]["elements"][0]["distance"]["value"]
        return meters / 1000.0, None
    except Exception as e:
        return None, f"Google route error: {e}"


def _route_osrm(o, d):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{o[1]},{o[0]};{d[1]},{d[0]}"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, params={"overview": "false"})
        resp.raise_for_status()
        data = resp.json()
        meters = data["routes"][0]["distance"]
        return meters / 1000.0, None
    except Exception as e:
        return None, f"OSRM route error: {e}"


def route_distance_km(origin: str, destination: str):
    """
    Returns (distance_km, method, debug_errors).
    method is one of: "google_route", "osrm_route", "haversine_estimate", "unavailable".
    """
    o_coords, o_errs = geocode(origin)
    d_coords, d_errs = geocode(destination)
    errors = [f"origin '{origin}': {e}" for e in o_errs] + [f"destination '{destination}': {e}" for e in d_errs]

    if not o_coords or not d_coords:
        return None, "unavailable", errors

    if GOOGLE_API_KEY:
        dist, err = _route_google(o_coords, d_coords)
        if dist is not None:
            return dist, "google_route", errors
        errors.append(err)

    dist, err = _route_osrm(o_coords, d_coords)
    if dist is not None:
        return dist, "osrm_route", errors
    errors.append(err)

    return haversine_km(o_coords, d_coords), "haversine_estimate", errors