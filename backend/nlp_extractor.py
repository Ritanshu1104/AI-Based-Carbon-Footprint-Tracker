import re


class ActivityExtractor:
    """Extract supported activities and normalized quantities from daily logs."""

    DISTANCE_UNITS = {
        "km": 1.0, "kilometer": 1.0, "kilometers": 1.0,
        "kilometre": 1.0, "kilometres": 1.0,
        "mi": 1.609344, "mile": 1.609344, "miles": 1.609344,
    }

    def __init__(self):
        number = r"(?P<quantity>\d+(?:\.\d+)?)"
        distance = rf"{number}\s*(?P<unit>km|kilomet(?:er|re)s?|mi|miles?)\b"
        self.patterns = [
            (rf"\b(?:flew|flight(?:\s+covering)?|took\s+(?:a\s+)?flight(?:\s+for|\s+covering)?)\s+{distance}", "Flight"),
            (rf"\b(?:travelled|traveled|commuted|rode|took\s+(?:a\s+)?)\s+{distance}\s+(?:by|on\s+(?:a|the))?\s*bus\b", "Bus"),
            (rf"\btook\s+(?:a|the)\s+bus\s+(?:for\s+)?{distance}", "Bus"),
            (rf"\b(?:travelled|traveled|commuted|rode|took\s+(?:a\s+)?)\s+{distance}\s+(?:by|on\s+(?:a|the))?\s*train\b", "Train"),
            (rf"\btook\s+(?:a|the)\s+train\s+(?:for\s+)?{distance}", "Train"),
            (rf"\b(?:drove|travelled|traveled|commuted)(?:\s+(?:my|a|the))?\s*(?:petrol\s+|diesel\s+|hybrid\s+|electric\s+)?(?:car|vehicle)?\s*{distance}", "Car"),
            (rf"\b(?:cycled|biked|rode\s+(?:my|a|the)?\s*(?:bike|bicycle)(?:\s+for)?)\s+{distance}", "Bike"),
            (rf"\b(?:walked|went\s+for\s+a)\s+{distance}(?:\s+walk)?", "Walking"),
        ]
        self.energy_pattern = re.compile(
            r"\b(?:watched\s+(?:tv|television)|used\s+(?:my\s+)?(?:computer|laptop)|"
            r"used\s+(?:the\s+)?(?:air\s+conditioner|ac))\s+for\s+"
            r"(?P<quantity>\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
            re.IGNORECASE,
        )

    @staticmethod
    def _vehicle_label(text):
        for fuel in ("petrol", "diesel", "hybrid", "electric"):
            if re.search(rf"\b{fuel}\b", text, re.IGNORECASE):
                return f"{fuel.title()} Car"
        return "Car"

    def extract_activities(self, text):
        if not isinstance(text, str):
            return []

        extracted = []
        occupied_spans = []
        for pattern, default_label in self.patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied_spans):
                    continue
                quantity = float(match.group("quantity"))
                source_unit = match.group("unit").lower()
                label = self._vehicle_label(match.group(0)) if default_label == "Car" else default_label
                extracted.append({
                    "label": label,
                    "quantity": round(quantity * self.DISTANCE_UNITS[source_unit], 3),
                    "unit": "km",
                    "source_text": match.group(0),
                })
                occupied_spans.append(match.span())

        for match in self.energy_pattern.finditer(text):
            extracted.append({
                "label": "Electricity", "quantity": float(match.group("quantity")),
                "unit": "hour", "source_text": match.group(0),
            })

        meal_patterns = (
            (r"\b(?:vegetarian meal|veg(?:etarian)? (?:lunch|dinner|meal))\b", "Vegetarian Meal"),
            (r"\b(?:chicken|chicken meal)\b", "Chicken Meal"),
        )
        for pattern, label in meal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted.append({"label": label, "quantity": 1.0, "unit": "meal", "source_text": match.group(0)})

        return sorted(extracted, key=lambda item: text.lower().find(item["source_text"].lower()))
