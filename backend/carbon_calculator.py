"""Uncertainty-aware footprint calculation with a reproducible audit trail."""

import os

import pandas as pd

from factor_store import FactorStore


class CarbonCalculator:
    def __init__(self, factor_store=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.factor_store = factor_store or FactorStore()
        demo_path = os.path.join(project_root, "data", "Carbon Emission.csv")
        self.avg_emission = float(pd.read_csv(demo_path)["CarbonEmission"].mean())

    def get_factor(self, label):
        resolved = self.factor_store.resolve(label)
        return resolved["factor_kg_co2e_per_unit"] if resolved else 0.0

    def calculate_footprint(self, activities):
        totals = {"point": 0.0, "low": 0.0, "high": 0.0}
        breakdown, unresolved, graph_nodes, graph_edges = [], [], [], []

        for activity in activities:
            label, quantity = activity["label"], activity.get("quantity")
            resolved = self.factor_store.resolve(label)
            event_id = activity.get("event_id", f"event-{len(graph_nodes) + 1}")
            graph_nodes.append({
                "id": event_id, "type": "activity-event", "label": label,
                "source_text": activity.get("source_text", ""),
            })
            for evidence_index, evidence in enumerate(activity.get("evidence", []), start=1):
                evidence_id = f"{event_id}:evidence:{evidence_index}"
                graph_nodes.append({
                    "id": evidence_id, "type": "evidence",
                    "label": evidence.get("kind", "evidence"),
                    "verification": evidence.get("verification", "unknown"),
                    "value": evidence.get("value"), "unit": evidence.get("unit"),
                    "reference": evidence.get("reference"),
                })
                graph_edges.append({"from": evidence_id, "to": event_id, "relation": "supports"})
            if quantity is None:
                unresolved.append({
                    "event_id": event_id, "activity": label,
                    "reason": "quantity-missing", "source_text": activity.get("source_text", ""),
                })
                continue
            if not resolved:
                unresolved.append({
                    "event_id": event_id, "activity": label,
                    "reason": "factor-missing", "source_text": activity.get("source_text", ""),
                })
                continue
            if str(activity.get("unit", "")).lower() != resolved["unit"].lower():
                unresolved.append({
                    "event_id": event_id, "activity": label, "reason": "unit-mismatch",
                    "expected_unit": resolved["unit"], "received_unit": activity.get("unit"),
                })
                continue

            point = quantity * resolved["factor_kg_co2e_per_unit"]
            low = quantity * resolved["low_kg_co2e_per_unit"]
            high = quantity * resolved["high_kg_co2e_per_unit"]
            totals["point"] += point
            totals["low"] += low
            totals["high"] += high

            factor_nodes = []
            for factor in resolved["candidates"]:
                factor_id = factor["factor_id"]
                factor_nodes.append(factor_id)
                if not any(node["id"] == factor_id for node in graph_nodes):
                    graph_nodes.append({
                        "id": factor_id, "type": "emission-factor",
                        "label": factor["activity"], "version": factor["version"],
                        "data_quality": factor["data_quality"],
                    })
                graph_edges.append({"from": event_id, "to": factor_id, "relation": "calculated-with"})

            confidence = self._confidence(activity, resolved)
            breakdown.append({
                "event_id": event_id, "activity": f"{label} ({quantity:g} {activity['unit']})",
                "label": label, "quantity": quantity, "unit": activity["unit"],
                "category": resolved["category"], "co2_kg": round(point, 3),
                "co2_range_kg": {"low": round(low, 3), "high": round(high, 3)},
                "factor_kg_co2e_per_unit": round(resolved["factor_kg_co2e_per_unit"], 6),
                "factor_range": {
                    "low": round(resolved["low_kg_co2e_per_unit"], 6),
                    "high": round(resolved["high_kg_co2e_per_unit"], 6),
                },
                "factor_candidates": resolved["candidates"], "factor_node_ids": factor_nodes,
                "source_text": activity.get("source_text", ""),
                "quantity_source": activity.get("quantity_source", "unknown"),
                "confidence": confidence, "evidence": activity.get("evidence", []),
            })

        result_id = "result-current"
        graph_nodes.append({
            "id": result_id, "type": "calculation-result",
            "label": "Current footprint estimate",
        })
        for item in breakdown:
            graph_edges.append({"from": item["event_id"], "to": result_id, "relation": "contributes-to"})

        return {
            "total_co2_kg": round(totals["point"], 3),
            "total_co2_range_kg": {
                "low": round(totals["low"], 3), "high": round(totals["high"], 3)
            },
            "confidence": self._overall_confidence(breakdown, unresolved),
            "breakdown": breakdown, "unresolved_activities": unresolved,
            "benchmark": self._get_benchmark(),
            "recommendations": self._recommendations(breakdown),
            "audit_graph": {"nodes": graph_nodes, "edges": graph_edges},
            "method": {
                "equation": "CO2e = activity quantity × emission factor",
                "uncertainty": "Reported bounds use the minimum and maximum candidate factor values.",
                "factor_dataset": self.factor_store.DATASET_NAME,
                "factor_version": self.factor_store.DATASET_VERSION,
                "publication_readiness": "research-prototype-only",
            },
        }

    @staticmethod
    def _confidence(activity, resolved):
        if any(item["data_quality"] == "illustrative-unverified" for item in resolved["candidates"]):
            return "low-factor-quality"
        return "medium" if activity.get("confidence") == "user-confirmed" else "low"

    @staticmethod
    def _overall_confidence(breakdown, unresolved):
        if unresolved:
            return "incomplete"
        if not breakdown:
            return "no-estimate"
        if any(item["confidence"] == "low-factor-quality" for item in breakdown):
            return "low-factor-quality"
        return "medium"

    def _recommendations(self, breakdown):
        suggestions = []
        alternatives = {"Petrol Car": "Train", "Diesel Car": "Train", "Car": "Train",
                        "Domestic Flight": "Train", "Flight": "Train"}
        for item in breakdown:
            alternative = alternatives.get(item["label"])
            if not alternative:
                continue
            alt = self.factor_store.resolve(alternative)
            if not alt:
                continue
            saving = max(0.0, item["co2_kg"] - item["quantity"] * alt["factor_kg_co2e_per_unit"])
            if saving > 0:
                suggestions.append({
                    "event_id": item["event_id"],
                    "message": f"If practical, using {alternative.lower()} for this trip could reduce the estimate.",
                    "estimated_saving_kg": round(saving, 3),
                    "decision_status": "directionally-stable" if item["factor_range"]["low"] > alt["high_kg_co2e_per_unit"] else "uncertain",
                    "basis": "Comparison uses the same illustrative project factor dataset.",
                })
        return suggestions

    def _get_benchmark(self):
        daily_avg = self.avg_emission / 365.0
        return {
            "annual_avg_kg": round(self.avg_emission, 2),
            "daily_avg_kg": round(daily_avg, 2),
            "data_quality": "exploratory-dataset-benchmark",
            "message": (
                f"Exploratory dataset benchmark: {self.avg_emission:.2f} kg CO2e/year "
                f"({daily_avg:.2f} kg/day). This is context, not a personal target."
            ),
        }
