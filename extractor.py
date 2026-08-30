"""
extractor.py

Turns a plain-English sentence typed by the user into one or more
structured "entries" that the rest of the pipeline (validators.py,
maps_service.py) can work with.

Design:
  1. FAST PATH (no API calls, no cost): a set of regex patterns that
     cover the common ways people describe travel/food/shopping/energy.
     This alone will handle the majority of real input.
  2. FALLBACK (optional): if the fast path finds nothing, and an
     Anthropic API key is available, we ask an LLM to return the same
     structured JSON. This catches free-form or oddly-phrased input
     without you having to write a regex for every possible sentence.

Every entry returned has this shape:
{
    "category": "travel" | "food" | "shopping" | "energy",
    "activity": str,          # e.g. "car", "beef", "t-shirt", "electricity"
    "quantity": float | None,
    "unit": str | None,
    "origin": str | None,     # travel only
    "destination": str | None,# travel only
    "raw_text": str,          # the original sentence, for auditing
    "source": "regex" | "llm"
}
Downstream validation (validators.py) fills in "valid", "issues", and
corrected/estimated values -- extraction's only job is to structure
the text, not to judge it.
"""

import os
import re
import json
from typing import List, Dict, Optional

from emission_factors import (
    TRANSPORT_MODES, FOOD_FACTORS, CLOTHING_FACTORS, ENERGY_FACTORS, MODE_ALIASES,
)


# ---------------------------------------------------------------------
# 1. Regex fast path
# ---------------------------------------------------------------------

# MODE_ALIASES (verb/synonym -> canonical TRANSPORT_MODES key) lives in
# emission_factors.py so it stays in sync with the actual mode list.
_TRAVEL_MODE_ALTS = "|".join(sorted((re.escape(k) for k in MODE_ALIASES.keys()),
                                     key=len, reverse=True))

# Stop words/phrases that end a travel clause -- keeps a multi-trip
# sentence ("...to Bhopal and my friend rode to Rajkot") from having its
# first clause swallow the second. Lookahead so it isn't consumed, and
# finditer can keep scanning past it for the next clause.
_CLAUSE_END = r"(?=[.,;]|$| today\b| yesterday\b| and\b| also\b| then\b)"

# "drove 20 km to work", "took a bus 15 km", "flew 500 km from Delhi to Mumbai"
_TRAVEL_DISTANCE_RE = re.compile(
    rf"\b(?:by |took (?:a|the) |went by )?({_TRAVEL_MODE_ALTS})[a-z]*\b"
    r".{0,30}?(\d+(?:\.\d+)?)\s*(km|kilometers?|kilometres?|mile?s?)",
    re.IGNORECASE,
)

# "drove from Indore to Bhopal", "flight from Delhi to Mumbai". The middle
# group captures whatever sits between the verb/mode and "from" (e.g. the
# "bike" in "drove bike from...") so we can prefer a more specific mode
# noun over a generic verb like "drove"/"drive".
_TRAVEL_OD_RE = re.compile(
    rf"\b({_TRAVEL_MODE_ALTS})[a-z]*\b(.{{0,20}}?)from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)"
    rf"{_CLAUSE_END}",
    re.IGNORECASE,
)

_FOOD_ALTS = "|".join(sorted(FOOD_FACTORS.keys(), key=len, reverse=True))
_FOOD_RE = re.compile(
    rf"(\d+(?:\.\d+)?)?\s*(g|gram?s?|kg|piece?s?|cups?|slices?|plates?|bowls?|tbsp|scoops?|bars?|bottles?)?\s*(?:of\s+)?"
    rf"({_FOOD_ALTS})",
    re.IGNORECASE,
)

_CLOTHING_ALTS = "|".join(sorted(CLOTHING_FACTORS.keys(), key=len, reverse=True))
_CLOTHING_RE = re.compile(
    rf"(\d+)?\s*({_CLOTHING_ALTS})s?\b",
    re.IGNORECASE,
)

_ENERGY_ALTS = "|".join(sorted(ENERGY_FACTORS.keys(), key=len, reverse=True))
_ENERGY_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s*(kwh|kg|litre?s?|liters?)\s*(?:of\s+)?({_ENERGY_ALTS})|"
    rf"({_ENERGY_ALTS}).{{0,15}}(\d+(?:\.\d+)?)\s*(kwh|kg|litre?s?|liters?)",
    re.IGNORECASE,
)

# Verbs that are ambiguous about *which* vehicle is meant ("drove",
# "drive"...) -- if one of these matches but a more specific mode noun
# (bike, scooter, auto, ...) appears in the text between the verb and
# "from"/the distance, we use that noun instead.
_GENERIC_MODE_VERBS = {"drove", "drive", "driving"}


def _resolve_mode(matched_alias: str, connector_text: str) -> str:
    """Prefers a specific mode noun in `connector_text` over a generic verb."""
    alias = matched_alias.lower()
    if alias in _GENERIC_MODE_VERBS and connector_text:
        for word, canonical in MODE_ALIASES.items():
            if word in _GENERIC_MODE_VERBS:
                continue
            if re.search(rf"\b{re.escape(word)}\b", connector_text, re.IGNORECASE):
                return canonical
    return MODE_ALIASES.get(alias, alias)


def _normalize_unit(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.lower().rstrip("s")
    mapping = {
        "kilometer": "km", "kilometre": "km", "mile": "mile",
        "gram": "g", "litre": "litre", "liter": "litre",
        "cup": "cup", "slice": "slice", "plate": "plate", "bowl": "bowl", "piece": "piece",
        "tbsp": "tbsp", "scoop": "scoop", "bar": "bar", "bottle": "bottle",
    }
    return mapping.get(u, u)


def regex_extract(text: str) -> List[Dict]:
    entries = []
    text_stripped = text.strip()

    # Travel with explicit origin/destination
    for m in _TRAVEL_OD_RE.finditer(text_stripped):
        mode = _resolve_mode(m.group(1), m.group(2))
        origin, dest = m.group(3).strip(), m.group(4).strip()
        entries.append({
            "category": "travel", "activity": mode, "quantity": None, "unit": "km",
            "origin": origin, "destination": dest,
            "raw_text": text_stripped, "source": "regex",
        })

    # Travel with explicit distance (only if no O/D match already covered it)
    if not entries:
        for m in _TRAVEL_DISTANCE_RE.finditer(text_stripped):
            mode = MODE_ALIASES.get(m.group(1).lower(), m.group(1).lower())
            qty = float(m.group(2))
            unit = _normalize_unit(m.group(3))
            entries.append({
                "category": "travel", "activity": mode, "quantity": qty, "unit": unit,
                "origin": None, "destination": None,
                "raw_text": text_stripped, "source": "regex",
            })

    # Food
    for m in _FOOD_RE.finditer(text_stripped):
        qty_raw, unit_raw, food = m.groups()
        entries.append({
            "category": "food", "activity": food.lower(),
            "quantity": float(qty_raw) if qty_raw else 1.0,
            "unit": _normalize_unit(unit_raw) or FOOD_FACTORS[food.lower()]["unit"],
            "origin": None, "destination": None,
            "raw_text": text_stripped, "source": "regex",
        })

    # Clothing / shopping
    for m in _CLOTHING_RE.finditer(text_stripped):
        qty_raw, item = m.groups()
        entries.append({
            "category": "shopping", "activity": item.lower(),
            "quantity": float(qty_raw) if qty_raw else 1.0,
            "unit": CLOTHING_FACTORS[item.lower()]["unit"],
            "origin": None, "destination": None,
            "raw_text": text_stripped, "source": "regex",
        })

    # Energy
    for m in _ENERGY_RE.finditer(text_stripped):
        g = m.groups()
        if g[0]:  # "5 litre of petrol"
            qty, unit, item = g[0], g[1], g[2]
        else:      # "petrol ... 5 litre"
            item, qty, unit = g[3], g[4], g[5]
        entries.append({
            "category": "energy", "activity": item.lower(),
            "quantity": float(qty), "unit": _normalize_unit(unit),
            "origin": None, "destination": None,
            "raw_text": text_stripped, "source": "regex",
        })

    return entries


# ---------------------------------------------------------------------
# 2. Optional LLM fallback (only runs if regex found nothing)
# ---------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You extract structured carbon-footprint activity data from one sentence of user input.
Return ONLY a JSON array (no prose, no markdown fences). Each element:
{"category": "travel|food|shopping|energy", "activity": string, "quantity": number|null,
 "unit": string|null, "origin": string|null, "destination": string|null}
If the sentence has no relevant activity, return [].
"""


def llm_extract(text: str, model: str = "claude-sonnet-4-6") -> List[Dict]:
    """
    Calls the Anthropic API to extract entries when regex can't.
    Requires ANTHROPIC_API_KEY to be set in the environment.
    Returns [] on any failure (missing key, network error, bad JSON)
    rather than raising, so callers can safely rely on the fast path
    as the default and treat this purely as a bonus.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    try:
        import anthropic  # local import so the module works without the package installed
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=500,
            system=_LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        raw = raw.strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        parsed = json.loads(raw)
        for e in parsed:
            e["raw_text"] = text
            e["source"] = "llm"
        return parsed
    except Exception:
        return []


def extract_entries(text: str, use_llm_fallback: bool = True) -> List[Dict]:
    """Main entry point: regex first, LLM only if regex found nothing."""
    entries = regex_extract(text)
    if not entries and use_llm_fallback:
        entries = llm_extract(text)
    return entries