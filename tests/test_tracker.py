import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import app  # noqa: E402
from carbon_calculator import CarbonCalculator  # noqa: E402
from nlp_extractor import ActivityExtractor  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
