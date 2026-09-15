"""Versioned, source-aware access to the project's emission-factor dataset."""

from __future__ import annotations

import os
import re

import pandas as pd


class FactorStore:
    """Expose point estimates, ranges, and provenance for every factor."""

    DATASET_NAME = "Project baseline emission-factor dataset"
    DATASET_VERSION = "1.0-research"

    LABEL_MAPPING = {
        "Domestic Flight": ["Domestic Flight"],
        "International Flight": ["International Flight"],
        "Flight": ["Domestic Flight", "International Flight"],
        "Bus": ["Bus"], "Train": ["Train"], "Metro": ["Metro"],
        "Taxi": ["Taxi"], "Motorcycle": ["Motorcycle"],
        "Scooter": ["Scooter"], "Auto Rickshaw": ["Auto Rickshaw"],
        "Car": ["Petrol Car", "Diesel Car", "Hybrid Car", "Electric Car"],
        "Petrol Car": ["Petrol Car"], "Diesel Car": ["Diesel Car"],
        "Hybrid Car": ["Hybrid Car"], "Electric Car": ["Electric Car"],
        "Bike": ["Bicycle"], "Bicycle": ["Bicycle"], "Walking": ["Walking"],
        "Chicken Meal": ["Chicken"], "Vegetarian Meal": ["Vegetarian Meal"],
        "Beef Meal": ["Beef"], "Fish Meal": ["Fish"],
        "Lamb Meal": ["Lamb"], "Pork Meal": ["Pork"],
        "Electricity": ["Electricity"],
    }

    def __init__(self, factors_path=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        factors_path = factors_path or os.path.join(
            project_root, "data", "Realistic_Emission_Factors_300.csv"
        )
        frame = pd.read_csv(factors_path)
        frame["base_activity"] = frame["Activity"].str.replace(
            r"\s+(Small|Medium|Large)\s+\d+", "", regex=True
        )
        self.records = {}
        for activity, group in frame.groupby("base_activity"):
            values = group["EmissionFactor_kgCO2e_per_unit"].astype(float)
            self.records[activity] = self._record(
                activity, float(values.mean()), float(values.min()), float(values.max()),
                self._infer_unit(activity), str(group.iloc[0].get("Category", self._category(activity))),
                f"Range is the spread across {len(group)} variants in the repository dataset.",
            )

        # These preserve the original prototype fallbacks and are explicitly
        # marked as placeholders until authoritative regional factors are added.
        self.records["Vegetarian Meal"] = self._record(
            "Vegetarian Meal", 2.0, 1.2, 3.0, "meal", "Food",
            "Unverified project placeholder retained from the original prototype.",
        )
        electricity = self._record(
            "Electricity", 0.675, 0.675, 0.675, "kWh", "Energy",
            "Weighted-average Indian Grid factor including renewable generation and captive injection.",
        )
        electricity.update({
            "factor_id": "cea-india-grid-average-fy2025-26",
            "source_name": "Central Electricity Authority CO2 Baseline Database for the Indian Power Sector",
            "source_url": "https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf",
            "version": "22.0", "geography": "India unified grid",
            "valid_from": "2025-04-01", "valid_to": "2026-03-31",
            "system_boundary": "grid electricity generation; weighted average",
            "gwp_basis": "CO2 only; factor reported directly as tCO2/MWh",
            "data_quality": "authoritative-government-publication",
        })
        self.records["Electricity"] = electricity

    def _record(self, activity, point, low, high, unit, category, notes):
        return {
            "factor_id": "pf-" + re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-"),
            "activity": activity,
            "factor_kg_co2e_per_unit": round(point, 6),
            "low_kg_co2e_per_unit": round(low, 6),
            "high_kg_co2e_per_unit": round(high, 6),
            "unit": unit, "category": category,
            "source_name": self.DATASET_NAME, "source_url": None,
            "version": self.DATASET_VERSION, "geography": "unspecified",
            "valid_from": None, "valid_to": None,
            "system_boundary": "unspecified", "gwp_basis": "unspecified",
            "data_quality": "illustrative-unverified", "notes": notes,
        }

    @staticmethod
    def _infer_unit(activity):
        return "meal" if activity in {"Beef", "Chicken", "Fish", "Lamb", "Pork"} else "km"

    @staticmethod
    def _category(activity):
        return "Food" if activity in {"Beef", "Chicken", "Fish", "Lamb", "Pork"} else "Transport"

    def candidates_for(self, label):
        names = self.LABEL_MAPPING.get(label, [label])
        return [dict(self.records[name]) for name in names if name in self.records]

    def resolve(self, label):
        candidates = self.candidates_for(label)
        if not candidates:
            return None
        points = [item["factor_kg_co2e_per_unit"] for item in candidates]
        return {
            "factor_kg_co2e_per_unit": sum(points) / len(points),
            "low_kg_co2e_per_unit": min(item["low_kg_co2e_per_unit"] for item in candidates),
            "high_kg_co2e_per_unit": max(item["high_kg_co2e_per_unit"] for item in candidates),
            "unit": candidates[0]["unit"], "category": candidates[0]["category"],
            "candidates": candidates,
        }

    def catalogue(self):
        return {
            "dataset": self.DATASET_NAME, "version": self.DATASET_VERSION,
            "warning": (
                "Most transport and food factors are illustrative and lack authoritative citations. "
                "Electricity uses the cited CEA Version 22.0 Indian-grid value."
            ),
            "factors": [dict(value) for value in self.records.values()],
        }
