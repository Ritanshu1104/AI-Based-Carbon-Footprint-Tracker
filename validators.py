"""
validators.py

Takes an extracted entry (see extractor.py) and returns a validated
copy with these extra fields:
    "valid": bool
    "issues": [str, ...]        # human-readable problems found, if any
    "confidence": "high"|"medium"|"low"
Numeric/unit fields may also be corrected in place (e.g. travel
distance replaced with the maps-derived figure).

Each category has its own validate_<category> function; validate_entry
just dispatches to the right one so extractor.py output can be piped
straight in.
"""

import difflib
from typing import Dict, List

from emission_factors import (
    TRANSPORT_MODES, TRANSPORT_DISTANCE_BOUNDS_KM,
    FOOD_FACTORS, CLOTHING_FACTORS, ENERGY_FACTORS,
)
import maps_service


def _fuzzy_match(name: str, choices) -> str:
    """Matches slightly-misspelled user input ('chiken') to a known key ('chicken')."""
    name = name.lower().strip()
    if name in choices:
        return name
    close = difflib.get_close_matches(name, choices, n=1, cutoff=0.7)
    return close[0] if close else None


def validate_travel(entry: Dict) -> Dict:
    issues: List[str] = []
    confidence = "high"

    mode = _fuzzy_match(entry.get("activity", ""), TRANSPORT_MODES.keys())
    if not mode:
        issues.append(f"Unrecognised travel mode '{entry.get('activity')}'.")
        entry["valid"] = False
        entry["issues"] = issues
        entry["confidence"] = "low"
        return entry
    entry["activity"] = mode

    # If we have an origin/destination, prefer the maps-derived distance --
    # it's more accurate than anything the user typed or guessed.
    if entry.get("origin") and entry.get("destination"):
        dist, method, debug_errors = maps_service.route_distance_km(entry["origin"], entry["destination"])
        if dist is not None:
            entry["quantity"] = round(dist, 1)
            entry["unit"] = "km"
            entry["distance_source"] = method
            if method == "haversine_estimate":
                issues.append("Could not fetch a road route; using straight-line estimate.")
                confidence = "medium"
            elif method != "google_route":
                confidence = "medium"  # OSRM demo server: fine, just not production-grade
        else:
            issues.append(
                f"Could not locate '{entry['origin']}' or '{entry['destination']}' on the map."
            )
            entry["debug_errors"] = debug_errors
            confidence = "low"

    # Sanity-check whatever distance we ended up with (user-given or maps-given)
    qty = entry.get("quantity")
    if qty is not None:
        lo, hi = TRANSPORT_DISTANCE_BOUNDS_KM.get(mode, (0, 100000))
        if not (lo <= qty <= hi):
            issues.append(f"{qty} km is unusual for '{mode}' (expected {lo}-{hi} km).")
            confidence = "low"
    else:
        issues.append("No distance found -- provide a distance or an origin/destination.")
        confidence = "low"

    entry["valid"] = qty is not None and confidence != "low"
    entry["issues"] = issues
    entry["confidence"] = confidence
    return entry


def validate_food(entry: Dict) -> Dict:
    issues, confidence = [], "high"
    food = _fuzzy_match(entry.get("activity", ""), FOOD_FACTORS.keys())
    if not food:
        issues.append(f"Unrecognised food item '{entry.get('activity')}'.")
        entry.update(valid=False, issues=issues, confidence="low")
        return entry
    entry["activity"] = food

    qty = entry.get("quantity") or 1.0
    if qty <= 0 or qty > 50:
        issues.append(f"Quantity {qty} looks off for '{food}'.")
        confidence = "low"
    entry["quantity"] = qty
    entry["unit"] = entry.get("unit") or FOOD_FACTORS[food]["unit"]
    entry["valid"] = confidence != "low"
    entry["issues"], entry["confidence"] = issues, confidence
    return entry


def validate_shopping(entry: Dict) -> Dict:
    issues, confidence = [], "high"
    item = _fuzzy_match(entry.get("activity", ""), CLOTHING_FACTORS.keys())
    if not item:
        issues.append(f"Unrecognised item '{entry.get('activity')}'.")
        entry.update(valid=False, issues=issues, confidence="low")
        return entry
    entry["activity"] = item

    qty = entry.get("quantity") or 1.0
    if qty <= 0 or qty > 100:
        issues.append(f"Quantity {qty} looks off for '{item}'.")
        confidence = "low"
    entry["quantity"] = qty
    entry["unit"] = entry.get("unit") or CLOTHING_FACTORS[item]["unit"]
    entry["valid"] = confidence != "low"
    entry["issues"], entry["confidence"] = issues, confidence
    return entry


def validate_energy(entry: Dict) -> Dict:
    issues, confidence = [], "high"
    item = _fuzzy_match(entry.get("activity", ""), ENERGY_FACTORS.keys())
    if not item:
        issues.append(f"Unrecognised energy type '{entry.get('activity')}'.")
        entry.update(valid=False, issues=issues, confidence="low")
        return entry
    entry["activity"] = item

    qty = entry.get("quantity")
    if qty is None or qty <= 0:
        issues.append("Missing or invalid quantity for energy entry.")
        entry.update(valid=False, issues=issues, confidence="low")
        return entry
    if qty > 10000:
        issues.append(f"Quantity {qty} looks unusually large for '{item}'.")
        confidence = "low"

    entry["valid"] = confidence != "low"
    entry["issues"], entry["confidence"] = issues, confidence
    return entry


_DISPATCH = {
    "travel": validate_travel,
    "food": validate_food,
    "shopping": validate_shopping,
    "energy": validate_energy,
}


def validate_entry(entry: Dict) -> Dict:
    fn = _DISPATCH.get(entry.get("category"))
    if not fn:
        entry["valid"] = False
        entry["issues"] = [f"Unknown category '{entry.get('category')}'."]
        entry["confidence"] = "low"
        return entry
    return fn(entry)


def validate_entries(entries: List[Dict]) -> List[Dict]:
    return [validate_entry(e) for e in entries]