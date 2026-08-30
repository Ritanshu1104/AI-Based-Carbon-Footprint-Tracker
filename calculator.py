"""
calculator.py

Turns a *validated* entry (see validators.py) into an estimated
kg CO2e figure, using the factors in emission_factors.py.

Kept intentionally simple: each factor is treated as "kg CO2e per one
unit of quantity, in the entry's default unit". Good enough for an
MVP tracker; swap in unit-conversion logic later if you need e.g.
grams-to-100g precision.
"""

from emission_factors import TRANSPORT_MODES, FOOD_FACTORS, CLOTHING_FACTORS, ENERGY_FACTORS


def estimate_co2_kg(entry: dict) -> float:
    if not entry.get("valid"):
        return 0.0

    category = entry.get("category")
    activity = entry.get("activity")
    qty = entry.get("quantity") or 0

    if category == "travel":
        factor = TRANSPORT_MODES.get(activity, {}).get("co2_per_km", 0)
        return round(factor * qty, 3)

    if category == "food":
        factor = FOOD_FACTORS.get(activity, {}).get("co2", 0)
        return round(factor * qty, 3)

    if category == "shopping":
        factor = CLOTHING_FACTORS.get(activity, {}).get("co2", 0)
        return round(factor * qty, 3)

    if category == "energy":
        factor = ENERGY_FACTORS.get(activity, {}).get("co2_per_unit", 0)
        return round(factor * qty, 3)

    return 0.0
