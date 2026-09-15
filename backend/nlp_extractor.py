"""Deterministic extraction of carbon-relevant events from daily activity text."""

import re
import uuid

from learning import CorrectionStore, NaiveBayesActivityClassifier


class ActivityExtractor:
    """Extract normalized activities while retaining their evidence."""

    DISTANCE_UNITS = {
        "km": 1.0, "kilometer": 1.0, "kilometers": 1.0,
        "kilometre": 1.0, "kilometres": 1.0,
        "mi": 1.609344, "mile": 1.609344, "miles": 1.609344,
    }
    ROUTE_MODES = {
        "car": "Car", "vehicle": "Car", "bus": "Bus", "train": "Train",
        "metro": "Metro", "taxi": "Taxi", "cab": "Taxi",
        "motorcycle": "Motorcycle", "motorbike": "Motorcycle",
        "scooter": "Scooter", "auto": "Auto Rickshaw",
        "rickshaw": "Auto Rickshaw", "bicycle": "Bike", "bike": "Bike",
        "walking": "Walking", "walk": "Walking",
    }

    def __init__(self, correction_store=None, classifier=None):
        self.correction_store = correction_store or CorrectionStore()
        self.classifier = classifier or NaiveBayesActivityClassifier()
        number = r"(?P<quantity>\d+(?:\.\d+)?)"
        distance = rf"{number}\s*(?P<unit>km|kilomet(?:er|re)s?|mi|miles?)\b"
        self.patterns = [
            (rf"\b(?:flew|flight(?:\s+covering)?|took\s+(?:a\s+)?flight(?:\s+for|\s+covering)?)\s+{distance}", "Flight"),
            (rf"\btook\s+(?:a|the)\s+bus\s+(?:for\s+)?{distance}", "Bus"),
            (rf"\b(?:travelled|traveled|commuted|rode)\s+{distance}\s+(?:by|using|on)\s+(?:a\s+|the\s+)?bus\b", "Bus"),
            (rf"\btook\s+(?:a|the)\s+train\s+(?:for\s+)?{distance}", "Train"),
            (rf"\b(?:travelled|traveled|commuted|rode)\s+{distance}\s+(?:by|using|on)\s+(?:a\s+|the\s+)?train\b", "Train"),
            (rf"\btook\s+(?:a|the)\s+metro\s+(?:for\s+)?{distance}", "Metro"),
            (rf"\b(?:travelled|traveled|commuted)\s+{distance}\s+(?:by|using|on)\s+(?:a\s+|the\s+)?metro\b", "Metro"),
            (rf"\b(?:took|used)\s+(?:a|the)\s+(?:taxi|cab)\s+(?:for\s+)?{distance}", "Taxi"),
            (rf"\b(?:travelled|traveled)\s+{distance}\s+(?:by|using)\s+(?:a\s+|the\s+)?(?:taxi|cab)\b", "Taxi"),
            (rf"\b(?:rode|used)\s+(?:my\s+|a\s+|the\s+)?(?:motorcycle|motorbike)(?:\s+for)?\s+{distance}", "Motorcycle"),
            (rf"\b(?:rode|used)\s+(?:my\s+|a\s+|the\s+)?scooter(?:\s+for)?\s+{distance}", "Scooter"),
            (rf"\b(?:took|used)\s+(?:an?\s+|the\s+)?(?:auto[- ]?rickshaw|rickshaw)(?:\s+for)?\s+{distance}", "Auto Rickshaw"),
            (rf"\b(?:drove|used)(?:\s+(?:my|a|the))?\s*(?:petrol\s+|diesel\s+|hybrid\s+|electric\s+)?(?:car|vehicle)(?:\s+for)?\s+{distance}", "Car"),
            (rf"\b(?:travelled|traveled)\s+{distance}\s+by\s+(?:my\s+|a\s+|the\s+)?(?:petrol\s+|diesel\s+|hybrid\s+|electric\s+)?car\b", "Car"),
            (rf"\b(?:cycled|biked|rode\s+(?:my\s+|a\s+|the\s+)?(?:bike|bicycle)(?:\s+for)?)\s+{distance}", "Bike"),
            (rf"\bwalked\s+{distance}", "Walking"),
            (rf"\bwent\s+for\s+a\s+{distance}\s+walk\b", "Walking"),
        ]
        self.kwh_pattern = re.compile(
            r"\b(?:used|consumed|electricity(?:\s+use)?(?:\s+was)?)\s+"
            r"(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>kwh|kilowatt[- ]hours?)\b",
            re.IGNORECASE,
        )
        self.device_pattern = re.compile(
            r"\b(?P<device>watched\s+(?:tv|television)|used\s+(?:my\s+)?(?:computer|laptop)|"
            r"used\s+(?:the\s+)?(?:air\s+conditioner|ac))\s+for\s+"
            r"(?P<quantity>\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
            re.IGNORECASE,
        )
        self.route_pattern = re.compile(
            r"\b(?:i\s+)?(?:went|travelled|traveled|commuted|drove|rode)?\s*from\s+"
            r"(?P<origin>[a-z][a-z .'-]{1,70}?)\s+to\s+"
            r"(?P<destination>[a-z][a-z .'-]{1,70}?)\s+"
            r"(?:by|in|using|on)\s+(?:a\s+|an\s+|my\s+|the\s+)?"
            r"(?P<mode>car|vehicle|bus|train|metro|taxi|cab|motorcycle|motorbike|"
            r"scooter|auto(?:[- ]rickshaw)?|rickshaw|bicycle|bike|walking|walk)\b",
            re.IGNORECASE,
        )

    @staticmethod
    def _vehicle_label(text):
        for fuel in ("petrol", "diesel", "hybrid", "electric"):
            if re.search(rf"\b{fuel}\b", text, re.IGNORECASE):
                return f"{fuel.title()} Car"
        return "Car"

    @staticmethod
    def _event(label, quantity, unit, source_text, **extra):
        event = {
            "event_id": str(uuid.uuid4()), "label": label,
            "quantity": quantity, "unit": unit, "source_text": source_text,
            "quantity_source": "user-text",
            "confidence": "high" if quantity is not None else "unresolved",
            "evidence": [{"kind": "user-statement", "value": source_text,
                          "verification": "unverified"}],
            "attributes": {},
        }
        event.update(extra)
        return event

    def extract_activities(self, text, user_id=None):
        if not isinstance(text, str):
            return []

        remembered = self.correction_store.lookup(user_id, text)
        if remembered:
            return [self._event(
                remembered["label"], remembered["quantity"], remembered["unit"], text,
                confidence="learned-correction", quantity_source="learned-correction",
                evidence=[{"kind": "user-correction-memory", "value": text,
                           "verification": "user-corrected", "uses": remembered["uses"]}],
            )]

        extracted, occupied = [], []
        for match in self.route_pattern.finditer(text):
            mode = match.group("mode").lower()
            if mode.startswith("auto"):
                mode = "auto"
            label = self.ROUTE_MODES[mode]
            extracted.append(self._event(
                label, None, "km", match.group(0), confidence="route-pending",
                attributes={
                    "route_origin": match.group("origin").strip().title(),
                    "route_destination": match.group("destination").strip().title(),
                    "route_mode": mode,
                },
            ))
            occupied.append(match.span())

        for pattern, default_label in self.patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                quantity = float(match.group("quantity"))
                source_unit = match.group("unit").lower()
                label = self._vehicle_label(match.group(0)) if default_label == "Car" else default_label
                extracted.append(self._event(
                    label, round(quantity * self.DISTANCE_UNITS[source_unit], 3),
                    "km", match.group(0),
                ))
                occupied.append(match.span())

        for match in self.kwh_pattern.finditer(text):
            extracted.append(self._event(
                "Electricity", float(match.group("quantity")), "kWh", match.group(0)
            ))

        for match in self.device_pattern.finditer(text):
            event = self._event(
                "Electricity", None, "kWh", match.group(0), confidence="unresolved",
                attributes={"device_description": match.group("device"),
                            "duration_hours": float(match.group("quantity"))},
            )
            event["evidence"].append({
                "kind": "duration", "value": float(match.group("quantity")),
                "unit": "hour", "verification": "user-text",
            })
            extracted.append(event)

        meal_patterns = (
            (r"\b(?:vegetarian meal|veg(?:etarian)? (?:lunch|dinner|meal))\b", "Vegetarian Meal"),
            (r"\bchicken(?:\s+meal)?\b", "Chicken Meal"),
            (r"\bbeef(?:\s+meal)?\b", "Beef Meal"),
            (r"\bfish(?:\s+meal)?\b", "Fish Meal"),
            (r"\blamb(?:\s+meal)?\b", "Lamb Meal"),
            (r"\bpork(?:\s+meal)?\b", "Pork Meal"),
        )
        for pattern, label in meal_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                extracted.append(self._event(label, 1.0, "meal", match.group(0)))

        incomplete = (
            (r"\b(?:drove|used)\s+(?:my\s+|a\s+|the\s+)?(?:car|vehicle)(?!\s+(?:for\s+)?\d)", "Car", "km"),
            (r"\b(?:took|rode)\s+(?:a\s+|the\s+)?bus(?!\s+(?:for\s+)?\d)", "Bus", "km"),
            (r"\b(?:took|rode)\s+(?:a\s+|the\s+)?train(?!\s+(?:for\s+)?\d)", "Train", "km"),
            (r"\b(?:flew|took\s+(?:a\s+)?flight)(?!\s+(?:for\s+|covering\s+)?\d)", "Flight", "km"),
        )
        for pattern, label, unit in incomplete:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                extracted.append(self._event(label, None, unit, match.group(0)))

        if not extracted:
            inferred = self._infer_unmatched(text)
            if inferred:
                extracted.append(inferred)

        ordered = sorted(extracted, key=lambda item: text.lower().find(item["source_text"].lower()))
        seen = {}
        for item in ordered:
            signature = (item["label"], item.get("quantity"), item.get("unit"),
                         " ".join(item["source_text"].lower().split()))
            if signature in seen:
                item.setdefault("attributes", {})["possible_duplicate_of"] = seen[signature]
                item["confidence"] = "possible-duplicate"
            else:
                seen[signature] = item["event_id"]
        return ordered

    def _infer_unmatched(self, text):
        prediction = self.classifier.predict(text)
        if not prediction or prediction["confidence"] < 0.45:
            return None
        label = prediction["label"]
        if "Meal" in label:
            quantity, unit = 1.0, "meal"
        else:
            distance = re.search(
                r"(\d+(?:\.\d+)?)\s*(km|kilomet(?:er|re)s?|mi|miles?)\b", text, re.IGNORECASE
            )
            if distance:
                quantity = float(distance.group(1)) * self.DISTANCE_UNITS[distance.group(2).lower()]
                unit = "km"
            else:
                quantity, unit = None, "kWh" if label == "Electricity" else "km"
        return self._event(
            label, round(quantity, 3) if quantity is not None else None, unit, text,
            confidence="model-inferred",
            evidence=[{"kind": "model-inference", "value": text,
                       "verification": "unverified", "model": prediction["model"],
                       "confidence": round(prediction["confidence"], 4)}],
            attributes={"model_confidence": round(prediction["confidence"], 4)},
        )
