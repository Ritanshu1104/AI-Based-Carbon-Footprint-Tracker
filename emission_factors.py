"""
emission_factors.py

Static reference data used by validators.py to sanity-check user input,
and by calculator.py for footprint math. Keep this file as the single
source of truth for "what categories/units/modes are valid" so
extraction, validation, and calculation all stay in sync.

Numbers are indicative averages (kg CO2e), broadly consistent with
DEFRA/IPCC-style per-km and per-serving figures. Swap in your own
vetted dataset when you have one -- the structure is what matters here.
"""

# --- Transport ---------------------------------------------------------
# NOTE on "bike": in everyday usage (especially Indian English) "bike"
# almost always means a motorcycle/scooter, not a pedal cycle. We use
# "motorbike" for the two-wheeler-with-engine case and "bicycle" for the
# pedal cycle, so "I rode my bike to work" is costed correctly instead
# of silently being treated as zero-emission.

TRANSPORT_MODES = {
    "car": {"co2_per_km": 0.192, "unit": "km"},          # average petrol/diesel mix
    "petrol_car": {"co2_per_km": 0.192, "unit": "km"},
    "diesel_car": {"co2_per_km": 0.171, "unit": "km"},
    "cng_car": {"co2_per_km": 0.140, "unit": "km"},
    "ev_car": {"co2_per_km": 0.053, "unit": "km"},       # grid-average electricity
    "motorbike": {"co2_per_km": 0.103, "unit": "km"},    # motorcycle/scooter, engine
    "scooter": {"co2_per_km": 0.083, "unit": "km"},
    "bicycle": {"co2_per_km": 0.0, "unit": "km"},        # pedal cycle
    "bus": {"co2_per_km": 0.089, "unit": "km"},
    "train": {"co2_per_km": 0.041, "unit": "km"},
    "metro": {"co2_per_km": 0.041, "unit": "km"},
    "flight": {"co2_per_km": 0.255, "unit": "km"},
    "auto": {"co2_per_km": 0.110, "unit": "km"},         # auto-rickshaw, petrol/CNG
    "e_rickshaw": {"co2_per_km": 0.020, "unit": "km"},
    "bike_taxi": {"co2_per_km": 0.090, "unit": "km"},
    "walk": {"co2_per_km": 0.0, "unit": "km"},
}

# Reasonable single-trip distance bounds per mode, used to flag
# obviously wrong numbers (e.g. "flew 3 km", "walked 400 km").
TRANSPORT_DISTANCE_BOUNDS_KM = {
    "car": (0.1, 2000), "petrol_car": (0.1, 2000), "diesel_car": (0.1, 2000),
    "cng_car": (0.1, 2000), "ev_car": (0.1, 1000),
    "motorbike": (0.1, 800), "scooter": (0.1, 300),
    "bicycle": (0.1, 300),
    "bus": (0.5, 3000),
    "train": (1, 3000),
    "metro": (0.5, 100),
    "flight": (50, 20000),
    "auto": (0.1, 100), "e_rickshaw": (0.1, 50),
    "bike_taxi": (0.1, 100),
    "walk": (0.05, 42),
}

# Maps how people actually phrase a mode (verbs, synonyms, Indian-English
# terms) to a canonical key in TRANSPORT_MODES above. Every value here
# MUST exist as a key in TRANSPORT_MODES.
MODE_ALIASES = {
    "car": "car", "cab": "car", "taxi": "car",
    "petrol car": "petrol_car", "diesel car": "diesel_car",
    "cng car": "cng_car", "cng": "cng_car",
    "ev": "ev_car", "electric car": "ev_car", "electric vehicle": "ev_car",
    "drove": "car", "drive": "car", "driving": "car",  # generic verb; extractor.py
                                                          # overrides this with a more
                                                          # specific noun if one appears
                                                          # nearby (e.g. "drove my bike").
    "bike": "motorbike", "biked": "motorbike", "rode": "motorbike",
    "motorbike": "motorbike", "motorcycle": "motorbike",
    "scooter": "scooter", "scooty": "scooter",
    "cycle": "bicycle", "cycled": "bicycle", "cycling": "bicycle", "bicycle": "bicycle",
    "bus": "bus",
    "train": "train", "rail": "train",
    "metro": "metro",
    "flight": "flight", "flew": "flight", "fly": "flight", "flying": "flight", "plane": "flight",
    "auto": "auto", "rickshaw": "auto",
    "e-rickshaw": "e_rickshaw", "e rickshaw": "e_rickshaw",
    "bike_taxi": "bike_taxi", "bike taxi": "bike_taxi",
    "walk": "walk", "walked": "walk", "walking": "walk",
}

# --- Food ------------------------------------------------------------------
# kg CO2e per typical serving/unit. Keys are matched fuzzily in validators.py.

FOOD_FACTORS = {
    "beef": {"co2": 6.61, "unit": "100g"},
    "mutton": {"co2": 7.50, "unit": "100g"},
    "lamb": {"co2": 6.87, "unit": "100g"},
    "pork": {"co2": 1.20, "unit": "100g"},
    "chicken": {"co2": 0.69, "unit": "100g"},
    "fish": {"co2": 0.60, "unit": "100g"},
    "prawns": {"co2": 3.40, "unit": "100g"},
    "egg": {"co2": 0.20, "unit": "piece"},
    "milk": {"co2": 0.32, "unit": "cup"},
    "curd": {"co2": 0.22, "unit": "cup"},
    "yogurt": {"co2": 0.22, "unit": "cup"},
    "paneer": {"co2": 1.50, "unit": "100g"},
    "cheese": {"co2": 2.10, "unit": "100g"},
    "butter": {"co2": 1.20, "unit": "tbsp"},
    "rice": {"co2": 0.40, "unit": "100g"},
    "wheat": {"co2": 0.14, "unit": "100g"},
    "bread": {"co2": 0.15, "unit": "slice"},
    "roti": {"co2": 0.10, "unit": "piece"},
    "chapati": {"co2": 0.10, "unit": "piece"},
    "dal": {"co2": 0.25, "unit": "bowl"},
    "lentils": {"co2": 0.25, "unit": "bowl"},
    "potato": {"co2": 0.06, "unit": "100g"},
    "onion": {"co2": 0.05, "unit": "100g"},
    "tomato": {"co2": 0.05, "unit": "100g"},
    "vegetables": {"co2": 0.20, "unit": "100g"},
    "fruits": {"co2": 0.15, "unit": "100g"},
    "apple": {"co2": 0.06, "unit": "piece"},
    "banana": {"co2": 0.08, "unit": "piece"},
    "mango": {"co2": 0.11, "unit": "piece"},
    "tea": {"co2": 0.05, "unit": "cup"},
    "coffee": {"co2": 0.09, "unit": "cup"},
    "soda": {"co2": 0.33, "unit": "bottle"},
    "cold drink": {"co2": 0.33, "unit": "bottle"},
    "biryani": {"co2": 1.80, "unit": "plate"},
    "dosa": {"co2": 0.35, "unit": "piece"},
    "idli": {"co2": 0.15, "unit": "piece"},
    "samosa": {"co2": 0.45, "unit": "piece"},
    "burger": {"co2": 2.50, "unit": "piece"},
    "pizza slice": {"co2": 0.90, "unit": "piece"},
    "ice cream": {"co2": 0.55, "unit": "scoop"},
    "chocolate": {"co2": 0.42, "unit": "bar"},
    "sugar": {"co2": 0.11, "unit": "100g"},
    "cooking oil": {"co2": 0.36, "unit": "tbsp"},
}

# --- Shopping / clothing ----------------------------------------------------

CLOTHING_FACTORS = {
    "t-shirt": {"co2": 5.0, "unit": "piece"},
    "shirt": {"co2": 5.5, "unit": "piece"},
    "kurta": {"co2": 6.0, "unit": "piece"},
    "saree": {"co2": 11.0, "unit": "piece"},
    "jeans": {"co2": 33.4, "unit": "piece"},
    "trousers": {"co2": 22.0, "unit": "piece"},
    "shoes": {"co2": 14.0, "unit": "pair"},
    "sandals": {"co2": 6.0, "unit": "pair"},
    "socks": {"co2": 1.5, "unit": "pair"},
    "jacket": {"co2": 25.0, "unit": "piece"},
    "sweater": {"co2": 18.0, "unit": "piece"},
    "dress": {"co2": 22.0, "unit": "piece"},
    "bag": {"co2": 9.0, "unit": "piece"},
    "cap": {"co2": 2.0, "unit": "piece"},
}

# --- Energy -------------------------------------------------------------

ENERGY_FACTORS = {
    "electricity": {"co2_per_unit": 0.82, "unit": "kWh"},
    "lpg": {"co2_per_unit": 2.98, "unit": "kg"},
    "cng": {"co2_per_unit": 2.54, "unit": "kg"},
    "petrol": {"co2_per_unit": 2.31, "unit": "litre"},
    "diesel": {"co2_per_unit": 2.68, "unit": "litre"},
    "coal": {"co2_per_unit": 2.42, "unit": "kg"},
    "firewood": {"co2_per_unit": 1.75, "unit": "kg"},
}

CATEGORIES = ("travel", "food", "shopping", "energy")

VALID_UNITS_BY_CATEGORY = {
    "travel": {"km", "mile", "miles"},
    "food": {"g", "100g", "kg", "piece", "cup", "slice", "plate", "bowl",
              "tbsp", "scoop", "bar", "bottle"},
    "shopping": {"piece", "pair"},
    "energy": {"kwh", "kg", "litre", "liter"},
}