"""Select and apply one useful clarification at a time."""

import re


class ClarificationEngine:
    """Rank missing facts by their estimated effect on the CO2e interval."""

    VEHICLE_OPTIONS = [
        {"value": "Petrol Car", "label": "Petrol car"},
        {"value": "Diesel Car", "label": "Diesel car"},
        {"value": "Hybrid Car", "label": "Hybrid car"},
        {"value": "Electric Car", "label": "Electric car"},
    ]
    FLIGHT_OPTIONS = [
        {"value": "Domestic Flight", "label": "Domestic flight"},
        {"value": "International Flight", "label": "International flight"},
    ]

    def __init__(self, factor_store):
        self.factor_store = factor_store

    DEVICE_POWER_RANGES_KW = {
        "tv": (0.05, 0.20), "television": (0.05, 0.20),
        "computer": (0.05, 0.50), "laptop": (0.03, 0.12),
        "air conditioner": (0.80, 2.50), "ac": (0.80, 2.50),
    }

    def _missing_quantity_metrics(self, activity):
        if activity["label"] != "Electricity":
            return {"expected_range_reduction_kg": 25.0, "effort_cost": 1.5,
                    "decision_sensitivity": 1.0, "basis": "distance-required"}
        description = activity.get("attributes", {}).get("device_description", "").lower()
        hours = activity.get("attributes", {}).get("duration_hours", 1.0)
        power_range = next(
            (value for key, value in self.DEVICE_POWER_RANGES_KW.items() if key in description),
            (0.05, 2.50),
        )
        factor = self.factor_store.resolve("Electricity")
        reduction = hours * power_range[1] * factor["high_kg_co2e_per_unit"]
        return {"expected_range_reduction_kg": round(reduction, 3), "effort_cost": 2.0,
                "decision_sensitivity": 0.8, "basis": "device-power-envelope"}

    def next_question(self, activities):
        questions = []
        for index, activity in enumerate(activities):
            label, quantity = activity["label"], activity.get("quantity")
            duplicate_of = activity.get("attributes", {}).get("possible_duplicate_of")
            if duplicate_of:
                questions.append({
                    "question_id": f"{activity['event_id']}:duplicate",
                    "event_id": activity["event_id"], "activity_index": index,
                    "field": "duplicate_confirmation",
                    "prompt": "Is this a separate activity or a duplicate entry?",
                    "input_type": "choice", "unit": None,
                    "options": [{"value": "keep", "label": "Separate activity"},
                                {"value": "remove", "label": "Remove duplicate"}],
                    "reason": "Counting the same event twice directly changes the total.",
                    "utility_score": 200.0,
                    "utility_metrics": {"expected_range_reduction_kg": None,
                                        "effort_cost": 0.3, "decision_sensitivity": 1.0,
                                        "basis": "duplicate-risk"},
                    "source_text": activity.get("source_text", ""),
                })
                continue
            if quantity is None:
                is_electricity = label == "Electricity"
                metrics = self._missing_quantity_metrics(activity)
                utility = (metrics["expected_range_reduction_kg"] *
                           (1 + metrics["decision_sensitivity"])) / metrics["effort_cost"]
                questions.append({
                    "question_id": f"{activity['event_id']}:quantity",
                    "event_id": activity["event_id"], "activity_index": index,
                    "field": "electricity_kwh" if is_electricity else "distance_km",
                    "prompt": (
                        "How many kWh did this device use? Check a smart plug, device label, "
                        "or electricity bill if available."
                        if is_electricity else
                        f"What distance did this {label.lower()} activity cover in kilometres?"
                    ),
                    "input_type": "number", "unit": "kWh" if is_electricity else "km",
                    "options": [], "reason": "A quantity is required before CO2e can be calculated.",
                    "utility_score": round(utility, 6), "utility_metrics": metrics,
                    "source_text": activity.get("source_text", ""),
                })
                continue

            resolved = self.factor_store.resolve(label)
            if label in {"Car", "Flight"} and resolved:
                width = quantity * (
                    resolved["high_kg_co2e_per_unit"] - resolved["low_kg_co2e_per_unit"]
                )
                effort_cost = 0.5
                sensitivity = 0.5
                utility = width * (1 + sensitivity) / effort_cost
                questions.append({
                    "question_id": f"{activity['event_id']}:subtype",
                    "event_id": activity["event_id"], "activity_index": index,
                    "field": "vehicle_type" if label == "Car" else "flight_type",
                    "prompt": (
                        "What type of car did you use?" if label == "Car" else
                        "Was this a domestic or international flight?"
                    ),
                    "input_type": "choice", "unit": None,
                    "options": self.VEHICLE_OPTIONS if label == "Car" else self.FLIGHT_OPTIONS,
                    "reason": f"This answer can narrow this activity's range by about {width:.2f} kg CO2e.",
                    "utility_score": round(utility, 6),
                    "utility_metrics": {
                        "expected_range_reduction_kg": round(width, 3),
                        "effort_cost": effort_cost,
                        "decision_sensitivity": sensitivity,
                        "basis": "candidate-factor-envelope",
                    },
                    "source_text": activity.get("source_text", ""),
                })

        return max(questions, key=lambda item: item["utility_score"], default=None)

    def apply_answer(self, activities, question, answer):
        if question is None:
            raise ValueError("There is no pending question")
        activity = next(
            (item for item in activities if item["event_id"] == question["event_id"]), None
        )
        if activity is None:
            raise ValueError("The activity for this question no longer exists")

        field = question["field"]
        answer_value = answer.get("value") if isinstance(answer, dict) else answer
        source_type = answer.get("source_type", "user-confirmed") if isinstance(answer, dict) else "user-confirmed"
        reference = answer.get("reference") if isinstance(answer, dict) else None
        allowed_sources = {"user-confirmed", "bill-or-meter", "route-service", "measured"}
        if source_type not in allowed_sources:
            raise ValueError("Unsupported evidence source")
        if field == "duplicate_confirmation":
            normalized = str(answer_value).strip().lower()
            if normalized == "remove":
                activities.remove(activity)
                return None
            if normalized != "keep":
                raise ValueError("Choose separate activity or remove duplicate")
            activity.setdefault("attributes", {}).pop("possible_duplicate_of", None)
            activity["confidence"] = "user-confirmed"
            return activity
        if field in {"distance_km", "electricity_kwh"}:
            match = re.search(r"\d+(?:\.\d+)?", str(answer_value))
            if not match or float(match.group(0)) <= 0:
                raise ValueError("Enter a number greater than zero")
            activity["quantity"] = float(match.group(0))
            activity["unit"] = "km" if field == "distance_km" else "kWh"
            activity["quantity_source"] = source_type
        else:
            allowed = {option["value"].lower(): option["value"] for option in question["options"]}
            normalized = str(answer_value).strip().lower()
            selected = allowed.get(normalized)
            if selected is None:
                selected = next(
                    (value for key, value in allowed.items() if normalized in key or key in normalized), None
                )
            if selected is None:
                raise ValueError("Choose one of the listed options")
            activity["label"] = selected

        activity["confidence"] = "user-confirmed"
        activity.setdefault("evidence", []).append({
            "kind": "clarification", "field": field, "value": answer_value,
            "verification": source_type, "reference": reference,
        })
        return activity
