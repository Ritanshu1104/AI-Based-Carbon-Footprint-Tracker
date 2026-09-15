"""Reproducible comparison of keyword and hybrid extraction approaches."""

import argparse
import json
import os
import re
import sys
import time

import pandas as pd


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from clarification import ClarificationEngine  # noqa: E402
from factor_store import FactorStore  # noqa: E402
from nlp_extractor import ActivityExtractor  # noqa: E402


KEYWORDS = {
    "Flight": ("flight", "flew"), "Bus": ("bus",), "Train": ("train",),
    "Car": ("car", "drove"), "Bike": ("bike", "cycled"), "Walking": ("walk",),
    "Chicken Meal": ("chicken",), "Vegetarian Meal": ("vegetarian", "veg"),
    "Electricity": ("tv", "computer", "conditioner", "kwh"),
}


def keyword_prediction(text):
    lowered = text.lower()
    for label, words in KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words):
            return label
    return None


def paraphrase(text):
    replacements = {
        "I travelled": "My journey covered", "I traveled": "My journey covered",
        "I took": "I went using", "I drove": "My commute in",
        "I ate": "My meal was", "I had": "For food I chose",
        "today": "during the day", "for lunch": "at lunchtime",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text


def evaluate(frame, extractor, transform=lambda value: value):
    methods = {"keyword": keyword_prediction,
               "hybrid": lambda text: (extractor.extract_activities(text) or [{}])[0].get("label")}
    results = {}
    for name, method in methods.items():
        start = time.perf_counter()
        correct = 0
        for _, row in frame.iterrows():
            correct += method(transform(row["text"])) == row["activity_label"]
        results[name] = {"correct": correct, "total": len(frame),
                         "accuracy": round(correct / len(frame), 4),
                         "elapsed_ms": round((time.perf_counter() - start) * 1000, 2)}
    return results


def clarification_metrics(extractor):
    clarifier = ClarificationEngine(FactorStore())
    scenarios = [
        "I drove my car 25 km", "I used the air conditioner for 4 hours",
        "I took a flight covering 900 km", "I drove my car to college",
    ]
    records = []
    for text in scenarios:
        activities = extractor.extract_activities(text)
        question = clarifier.next_question(activities)
        records.append({"text": text, "activity_count": len(activities),
                        "question_field": question["field"] if question else None,
                        "utility_score": question["utility_score"] if question else 0})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    frame = pd.read_csv(os.path.join(ROOT, "data", "Daily_Activity_Text_Dataset.csv"))
    extractor = ActivityExtractor()
    report = {
        "dataset": "Daily_Activity_Text_Dataset.csv",
        "in_distribution": evaluate(frame, extractor),
        "rule_challenging_paraphrases": evaluate(frame, extractor, paraphrase),
        "clarification_scenarios": clarification_metrics(extractor),
        "limitations": [
            "The repository dataset contains templated examples rather than independent human logs.",
            "Paraphrases are deterministic stress tests, not a held-out external corpus.",
            "A publication needs independent annotation and confidence intervals across multiple runs.",
        ],
    }
    output = json.dumps(report, indent=2)
    print(output)
    if args.output:
        output_path = os.path.abspath(args.output)
        if not output_path.startswith(os.path.join(ROOT, "experiments", "results") + os.sep):
            raise ValueError("Experiment output must stay under experiments/results")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")


if __name__ == "__main__":
    main()
