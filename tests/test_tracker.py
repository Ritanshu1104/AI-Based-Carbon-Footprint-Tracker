import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

import pandas as pd


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import app  # noqa: E402
from carbon_calculator import CarbonCalculator  # noqa: E402
from clarification import ClarificationEngine  # noqa: E402
from factor_store import FactorStore  # noqa: E402
from forecasting import FootprintForecaster  # noqa: E402
from journal import JournalRepository  # noqa: E402
from learning import CorrectionStore  # noqa: E402
from nlp_extractor import ActivityExtractor  # noqa: E402
from ocr_evidence import BillOcrService  # noqa: E402
from routing import RouteEvidenceService  # noqa: E402
from security import AuthRepository, DataCipher  # noqa: E402


class ActivityExtractorTests(unittest.TestCase):
    def setUp(self):
        self.extractor = ActivityExtractor()

    def test_readme_train_example(self):
        activities = self.extractor.extract_activities("I took a train for 300 km.")
        self.assertEqual(activities[0]["label"], "Train")
        self.assertEqual(activities[0]["quantity"], 300.0)

    def test_miles_are_normalized_and_fuel_is_preserved(self):
        activities = self.extractor.extract_activities("I drove my electric car 10 miles.")
        self.assertEqual(activities[0]["label"], "Electric Car")
        self.assertAlmostEqual(activities[0]["quantity"], 16.093, places=3)

    def test_multiple_activities_keep_text_order(self):
        activities = self.extractor.extract_activities(
            "Ate chicken, travelled 12 km by bus and watched TV for 2 hours."
        )
        self.assertEqual([item["label"] for item in activities], ["Chicken Meal", "Bus", "Electricity"])

    def test_project_dataset_labels_are_all_recognized(self):
        frame = pd.read_csv(os.path.join(ROOT, "data", "Daily_Activity_Text_Dataset.csv"))
        failures = []
        for _, row in frame.iterrows():
            activities = self.extractor.extract_activities(row["text"])
            if not activities or activities[0]["label"] != row["activity_label"]:
                failures.append(row["text"])
        self.assertEqual(failures, [])

    def test_device_hours_are_not_misrepresented_as_kwh(self):
        activity = self.extractor.extract_activities("I used the air conditioner for 4 hours")[0]
        self.assertEqual(activity["label"], "Electricity")
        self.assertIsNone(activity["quantity"])
        self.assertEqual(activity["attributes"]["duration_hours"], 4.0)

    def test_bus_phrase_is_not_misclassified_as_car(self):
        activity = self.extractor.extract_activities("I commuted 14 km using the bus")[0]
        self.assertEqual(activity["label"], "Bus")

    def test_used_my_car_phrase_is_recognized(self):
        activity = self.extractor.extract_activities("I used my car for 9 km today")[0]
        self.assertEqual(activity["label"], "Car")
        self.assertEqual(activity["quantity"], 9.0)

    def test_expanded_transport_and_food_coverage(self):
        activities = self.extractor.extract_activities(
            "I took an auto rickshaw for 6 km and ate fish for dinner"
        )
        self.assertEqual([item["label"] for item in activities], ["Auto Rickshaw", "Fish Meal"])

    def test_hybrid_classifier_handles_unseen_word_order(self):
        activity = self.extractor.extract_activities("Across 12 km, the bus carried me home")[0]
        self.assertEqual(activity["label"], "Bus")
        self.assertEqual(activity["quantity"], 12.0)
        self.assertEqual(activity["confidence"], "model-inferred")

    def test_possible_duplicate_is_flagged(self):
        activities = self.extractor.extract_activities("I walked 2 km. Later: I walked 2 km.")
        self.assertEqual(len(activities), 2)
        self.assertIn("possible_duplicate_of", activities[1]["attributes"])
        question = ClarificationEngine(FactorStore()).next_question(activities)
        self.assertEqual(question["field"], "duplicate_confirmation")

    def test_route_places_and_mode_are_extracted_without_manual_distance(self):
        activity = self.extractor.extract_activities(
            "I went from Indore to Bhopal in car"
        )[0]
        self.assertEqual(activity["label"], "Car")
        self.assertIsNone(activity["quantity"])
        self.assertEqual(activity["attributes"]["route_origin"], "Indore")
        self.assertEqual(activity["attributes"]["route_destination"], "Bhopal")


class CarbonCalculatorTests(unittest.TestCase):
    def test_specific_vehicle_uses_specific_factor(self):
        calculator = CarbonCalculator()
        self.assertNotEqual(calculator.get_factor("Electric Car"), calculator.get_factor("Petrol Car"))

    def test_breakdown_exposes_factor_for_audit(self):
        result = CarbonCalculator().calculate_footprint([
            {"label": "Bus", "quantity": 2.0, "unit": "km", "source_text": "2 km by bus"}
        ])
        self.assertIn("factor_kg_co2e_per_unit", result["breakdown"][0])
        self.assertEqual(result["breakdown"][0]["source_text"], "2 km by bus")

    def test_result_exposes_range_provenance_and_graph(self):
        result = CarbonCalculator().calculate_footprint([
            {"event_id": "event-1", "label": "Car", "quantity": 10.0,
             "unit": "km", "source_text": "car for 10 km"}
        ])
        self.assertLess(result["total_co2_range_kg"]["low"], result["total_co2_range_kg"]["high"])
        factor = result["breakdown"][0]["factor_candidates"][0]
        self.assertIn("version", factor)
        self.assertIn("data_quality", factor)
        self.assertGreater(len(result["audit_graph"]["edges"]), 0)

    def test_indian_electricity_uses_current_cea_record(self):
        factor = FactorStore().candidates_for("Electricity")[0]
        self.assertEqual(factor["factor_kg_co2e_per_unit"], 0.675)
        self.assertEqual(factor["version"], "22.0")
        self.assertEqual(factor["geography"], "India unified grid")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_rejects_non_json_body(self):
        response = self.client.post("/api/analyze", data="hello", content_type="text/plain")
        self.assertEqual(response.status_code, 400)

    def test_analyzes_valid_log(self):
        response = self.client.post("/api/analyze", json={"text": "I took a train for 5 km"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["extracted_activities"][0]["label"], "Train")

    def test_daily_log_analyzes_each_row_and_keeps_unsupported_entries(self):
        response = self.client.post("/api/analyze", json={"entries": [
            "I took a train for 5 km.",
            "I used 3 kWh of electricity.",
            "I replaced my smartphone.",
        ]})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["breakdown"]), 2)
        self.assertEqual(payload["unrecognized_entries"][0]["source_text"],
                         "I replaced my smartphone.")

    def test_daily_log_rejects_more_than_thirty_rows(self):
        response = self.client.post("/api/analyze", json={"entries": ["walked"] * 31})
        self.assertEqual(response.status_code, 400)

    def test_generic_car_is_clarified_then_completed(self):
        first = self.client.post("/api/analyze", json={"text": "I drove my car 10 km"})
        payload = first.get_json()
        self.assertEqual(payload["status"], "needs_clarification")
        self.assertEqual(payload["question"]["field"], "vehicle_type")
        second = self.client.post("/api/clarify", json={
            "session_id": payload["session_id"],
            "question_id": payload["question"]["question_id"],
            "answer": "Electric Car",
        })
        resolved = second.get_json()
        self.assertEqual(resolved["status"], "complete")
        self.assertEqual(resolved["breakdown"][0]["label"], "Electric Car")

    def test_appliance_hours_request_kwh(self):
        response = self.client.post("/api/analyze", json={
            "text": "I used the air conditioner for 3 hours"
        })
        payload = response.get_json()
        self.assertEqual(payload["question"]["field"], "electricity_kwh")
        self.assertEqual(payload["unresolved_activities"][0]["reason"], "quantity-missing")
        self.assertIn("expected_range_reduction_kg", payload["question"]["utility_metrics"])

        resolved = self.client.post("/api/clarify", json={
            "session_id": payload["session_id"],
            "question_id": payload["question"]["question_id"],
            "answer": {"value": 2.4, "source_type": "measured", "reference": "smart plug"},
        }).get_json()
        self.assertEqual(resolved["status"], "complete")
        self.assertEqual(resolved["breakdown"][0]["quantity_source"], "measured")
        self.assertEqual(resolved["breakdown"][0]["evidence"][-1]["reference"], "smart plug")

    def test_factor_catalogue_discloses_quality_limitation(self):
        response = self.client.get("/api/factors")
        self.assertEqual(response.status_code, 200)
        self.assertIn("illustrative", response.get_json()["warning"].lower())

    def test_frontend_is_served_by_backend(self):
        response = self.client.get("/")
        content = response.data
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Carbon Evidence Lab", content)

    def test_capabilities_report_integrated_components(self):
        payload = self.client.get("/api/capabilities").get_json()
        self.assertIn("routing", payload)
        self.assertIn("bill_ocr", payload)
        self.assertTrue(payload["forecasting"]["arima_available"])

    def test_account_and_encrypted_journal_flow(self):
        username = "test_" + uuid.uuid4().hex[:12]
        registered = self.client.post("/api/auth/register", json={
            "username": username, "password": "correct-horse-battery"
        })
        self.assertEqual(registered.status_code, 201)
        token = registered.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        analyzed = self.client.post("/api/analyze", json={"text": "I took a train for 5 km"}).get_json()
        saved = self.client.post("/api/journal", headers=headers,
                                 json={"session_id": analyzed["session_id"]})
        self.assertEqual(saved.status_code, 201)
        listing = self.client.get("/api/journal", headers=headers).get_json()
        self.assertEqual(listing["count"], 1)
        entry_id = listing["entries"][0]["entry_id"]
        self.client.delete(f"/api/journal/{entry_id}", headers=headers)

    def test_journal_rejects_anonymous_access(self):
        self.assertEqual(self.client.get("/api/journal").status_code, 401)

    def test_route_evidence_updates_anonymous_session_after_consent(self):
        analyzed = self.client.post(
            "/api/analyze", json={"text": "I drove my car to college"}
        ).get_json()
        event_id = analyzed["extracted_activities"][0]["event_id"]
        provider_response = {"code": "Ok", "routes": [{
            "distance": 7400.0, "duration": 900.0
        }]}
        with patch("app.routes._json", return_value=provider_response):
            response = self.client.post("/api/evidence/route", json={
                "session_id": analyzed["session_id"], "event_id": event_id,
                "provider": "osrm", "consent_external_processing": True,
                "origin": {"latitude": 12.9, "longitude": 77.5},
                "destination": {"latitude": 13.0, "longitude": 77.6},
            })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["extracted_activities"][0]["quantity"], 7.4)
        self.assertEqual(payload["route_evidence"]["provider"], "Open Source Routing Machine")


class JournalTests(unittest.TestCase):
    def test_journal_persists_and_builds_rolling_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            cipher = DataCipher(os.path.join(directory, "key"))
            repository = JournalRepository(os.path.join(directory, "journal.db"), cipher)
            calculator = CarbonCalculator()
            result = calculator.calculate_footprint([
                {"event_id": "e1", "label": "Train", "quantity": 10.0,
                 "unit": "km", "source_text": "train 10 km"}
            ])
            for day in ("2026-09-13", "2026-09-14", "2026-09-15"):
                repository.save("user-1", "train 10 km", result, day)
            listing = repository.list("user-1")
            self.assertEqual(len(listing), 3)
            self.assertEqual(listing[0]["entry_date"], "2026-09-15")
            repository.set_goal("user-1", "2026-09", 10)
            dashboard = repository.dashboard("user-1", "2026-09")
            self.assertEqual(dashboard["entry_count"], 3)
            self.assertIsNotNone(dashboard["goal_progress_percent"])
            with open(os.path.join(directory, "journal.db"), "rb") as database_file:
                self.assertNotIn(b"train 10 km", database_file.read())


class ProviderAndSecurityTests(unittest.TestCase):
    def test_osrm_route_requires_consent_and_returns_distance(self):
        service = RouteEvidenceService(osrm_url="https://routing.invalid")
        with self.assertRaises(ValueError):
            service.route({"provider": "osrm"})
        service._json = lambda _request: {"code": "Ok", "routes": [{
            "distance": 12345.0, "duration": 900.0
        }]}
        result = service.route({
            "provider": "osrm", "consent_external_processing": True,
            "origin": {"latitude": 12.9, "longitude": 77.5},
            "destination": {"latitude": 13.0, "longitude": 77.6},
        })
        self.assertEqual(result["distance_km"], 12.345)

    def test_osrm_accepts_readable_degree_coordinates(self):
        service = RouteEvidenceService(osrm_url="https://routing.invalid")
        service._json = lambda _request: {"code": "Ok", "routes": [{
            "distance": 191200.0, "duration": 10000.0
        }]}
        result = service.route({
            "provider": "osrm", "consent_external_processing": True,
            "origin": "latitude 22.7196° N and longitude 75.8577° E",
            "destination": "latitude 23.2599° N and longitude 77.4126° E",
        })
        self.assertEqual(result["distance_km"], 191.2)

    def test_coordinate_parser_applies_south_and_west_signs(self):
        self.assertEqual(RouteEvidenceService._coordinates("33.9 S, 18.4 E", "origin"),
                         (-33.9, 18.4))

    def test_google_route_returns_polyline_and_alternatives(self):
        service = RouteEvidenceService(google_key="test-key")
        service._json = lambda _request: {"routes": [
            {"distanceMeters": 10000, "duration": "900s",
             "polyline": {"encodedPolyline": "first"}},
            {"distanceMeters": 11250, "duration": "1020s",
             "polyline": {"encodedPolyline": "second"}},
        ]}
        result = service.route({
            "provider": "google", "consent_external_processing": True,
            "origin": "Indore, Madhya Pradesh", "destination": "Bhopal, Madhya Pradesh",
            "mode": "driving", "route_index": 1,
        })
        self.assertEqual(result["distance_km"], 11.25)
        self.assertEqual(result["selected_index"], 1)
        self.assertEqual(result["encoded_polyline"], "second")
        self.assertEqual(len(result["alternatives"]), 2)

    def test_google_place_autocomplete_normalizes_suggestions(self):
        service = RouteEvidenceService(google_key="test-key")
        service._json = lambda _request: {"suggestions": [{"placePrediction": {
            "placeId": "place-1", "text": {"text": "Bhopal, Madhya Pradesh, India"}
        }}]}
        suggestions = service.autocomplete("Bhopal", "session-1")
        self.assertEqual(suggestions, [{
            "place_id": "place-1", "text": "Bhopal, Madhya Pradesh, India"
        }])

    def test_bill_text_extracts_kwh_and_meter_difference(self):
        service = BillOcrService()
        direct = service.extract_from_text("Energy consumed: 245 kWh")
        self.assertEqual(direct["recommended_kwh"], 245.0)
        readings = service.extract_from_text("Previous meter reading 1000 Current meter reading 1125")
        self.assertIn(125.0, [item["kwh"] for item in readings["candidates"]])

    def test_forecasting_reports_fallback_and_arima_capability(self):
        forecaster = FootprintForecaster()
        result = forecaster.forecast([1, 2, 1.5, 2.5], steps=2)
        self.assertEqual(result["method"], "rolling-mean-fallback")
        self.assertEqual(len(result["points"]), 2)

    def test_arima_path_returns_probabilistic_interval(self):
        result = FootprintForecaster().forecast(
            [1.0, 1.8, 1.2, 2.4, 1.7, 2.8, 2.1, 3.2, 2.6, 3.7], steps=3
        )
        self.assertEqual(result["method"], "ARIMA(1,1,1)")
        self.assertEqual(len(result["points"]), 3)
        self.assertLessEqual(result["points"][0]["low_kg"], result["points"][0]["high_kg"])

    def test_passwords_tokens_and_ciphertext_are_not_stored_plainly(self):
        with tempfile.TemporaryDirectory() as directory:
            cipher = DataCipher(os.path.join(directory, "key"))
            encrypted = cipher.encrypt("private activity")
            self.assertNotIn("private activity", encrypted)
            self.assertEqual(cipher.decrypt(encrypted), "private activity")
            auth = AuthRepository(os.path.join(directory, "auth.db"))
            auth.register("local_user", "long-enough-password")
            login = auth.login("local_user", "long-enough-password")
            self.assertEqual(auth.resolve_token(login["token"])["username"], "local_user")

    def test_authenticated_correction_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CorrectionStore(os.path.join(directory, "learning.db"),
                                    DataCipher(os.path.join(directory, "key")))
            store.save("user-1", "my unusual commute", "Bus", 8, "km")
            remembered = store.lookup("user-1", "My unusual commute")
            self.assertEqual(remembered["label"], "Bus")
            self.assertIsNone(store.lookup("user-2", "My unusual commute"))


if __name__ == "__main__":
    unittest.main()
