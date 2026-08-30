# Text-input module for the carbon footprint tracker

## Files
- `emission_factors.py` — reference data: valid transport modes, food/clothing/energy
  factors, and sanity-check bounds. Edit this as your single source of truth.
- `extractor.py` — turns a sentence into structured entries. Regex handles common
  phrasings for free (no API cost); if nothing matches, it optionally falls back
  to an LLM call (only if `ANTHROPIC_API_KEY` is set) for oddly-phrased input.
- `maps_service.py` — geocodes place names and gets route distance. Uses free
  OpenStreetMap/OSRM by default; automatically switches to Google Maps if
  `GOOGLE_MAPS_API_KEY` is set (more accurate, needs billing).
- `validators.py` — checks each entry against known categories/units, fuzzy-matches
  typos ("chiken" → "chicken"), and for travel, calls `maps_service` to replace/verify
  the distance so users can just say "drove from Indore to Bhopal" instead of typing km.
- `example_usage.py` — run `python3 example_usage.py` to see the full pipeline.

## How to use in your app
```python
from extractor import extract_entries
from validators import validate_entries

entries = validate_entries(extract_entries(user_text))
# each entry has: category, activity, quantity, unit, valid, issues, confidence
for e in entries:
    if e["valid"]:
        save_to_db(e)
    else:
        show_user_a_correction_prompt(e["issues"])
```

## Notes on the maps piece
- The free OSRM demo server is rate-limited and explicitly **not for production**
  use — fine for your prototype/demo, but before real users, either self-host OSRM
  or switch to Google's Distance Matrix API by setting `GOOGLE_MAPS_API_KEY`.
- If geocoding/routing fails (no internet, place not found), the module falls back
  to a straight-line (haversine) estimate and flags `confidence: "medium"/"low"`
  so your UI can show "approximate distance used."

## Extending it
- Add new activities/units by editing `emission_factors.py` only — extractor and
  validators both read from it, so nothing else needs to change.
- Add new sentence patterns in `extractor.py`'s regex section, or just rely on the
  LLM fallback for anything you haven't written a pattern for yet.
