"""
example_usage.py

Run this to see the whole pipeline: raw text -> extracted entries ->
validated entries. This is what your app's backend endpoint
(e.g. POST /log-activity) would call.
"""

from extractor import extract_entries
from validators import validate_entries


def process_user_text(text: str):
    entries = extract_entries(text)
    validated = validate_entries(entries)
    return validated


if __name__ == "__main__":
    samples = [
        "I drove from Indore to Bhopal today",
        "took a bus 15 km to college",
        "I ate 2 eggs and a burger for lunch",
        "bought 2 t-shirts and a pair of shoes",
        "used 5 litre of petrol this week",
        "flew 3 km to the moon",          # should get flagged as invalid
    ]
    for s in samples:
        print(f"\nINPUT: {s}")
        for entry in process_user_text(s):
            print(" ->", entry)
