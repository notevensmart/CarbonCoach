from __future__ import annotations

from app.chains.classify_chain import classify_activities
from app.services.climatiq_api import ClimatiqClient, extract_unit_info
from app.services.param_utils import FallbackEstimator, JournalParameterExtractor
from app.embedder import retrieve_best_activities


class CarbonPipeline:
    def __init__(
        self,
        parameter_extractor: JournalParameterExtractor | None = None,
        climatiq_client: ClimatiqClient | None = None,
        fallback_estimator: FallbackEstimator | None = None,
    ) -> None:
        self.parameter_extractor = parameter_extractor or JournalParameterExtractor()
        self.climatiq_client = climatiq_client or ClimatiqClient()
        self.fallback_estimator = fallback_estimator or FallbackEstimator()

    def run(self, journal_entry: str) -> dict:
        activities = classify_activities(journal_entry)
        labels = [label for label, _ in activities]
        matched_dict = retrieve_best_activities(labels) if labels else {}

        total_emissions = 0.0
        details = []

        for label, category in activities:
            detail = self._estimate_activity(journal_entry, label, category, matched_dict)
            if detail["co2e"] is not None:
                total_emissions += detail["co2e"]
            details.append(detail)

        total = round(total_emissions, 3)
        return {
            "result": {
                "co2e": total,
                "unit": "kg",
                "details": details,
                "summary": f"Total emissions: {total} kg CO2e",
            }
        }

    def _estimate_activity(
        self,
        journal_entry: str,
        label: str,
        category: str,
        matched_dict: dict,
    ) -> dict:
        detail = {
            "label": label,
            "category": category,
            "activity": None,
            "activity_id": None,
            "unit_type": None,
            "parameters": None,
            "parameter_source": None,
            "parameter_confidence": None,
            "co2e": None,
            "unit": None,
            "source": None,
            "status": "error",
            "error_message": "",
        }

        match = matched_dict.get(label)
        if not match:
            detail["error_message"] = f"No match found for '{label}'"
            return detail

        activity_id = match.get("activity_id")
        activity_name = match.get("activity_name")
        detail["activity"] = activity_name
        detail["activity_id"] = activity_id

        if not activity_id:
            detail["error_message"] = f"No activity ID found for '{activity_name}'"
            return detail

        unit_type, _ = extract_unit_info(activity_id)
        detail["unit_type"] = unit_type
        parameter_result = self.parameter_extractor.extract(
            unit_type=unit_type,
            journal_entry=journal_entry,
            label=label,
            category=category,
        )
        detail["parameters"] = parameter_result.parameters
        detail["parameter_source"] = parameter_result.source
        detail["parameter_confidence"] = parameter_result.confidence
        detail["parameter_notes"] = parameter_result.notes

        climatiq_result = self.climatiq_client.estimate(activity_id, parameter_result.parameters)
        if climatiq_result.ok:
            detail["co2e"] = round(float(climatiq_result.co2e), 3)
            detail["unit"] = climatiq_result.co2e_unit or "kg"
            detail["source"] = climatiq_result.source
            detail["status"] = "ok"
            return detail

        fallback = self.fallback_estimator.estimate(
            category=category,
            unit_type=unit_type,
            parameters=parameter_result.parameters,
        )
        detail["co2e"] = fallback["co2e"]
        detail["unit"] = fallback["co2e_unit"]
        detail["source"] = fallback["source"]
        detail["fallback_factor"] = fallback["factor"]
        detail["status"] = "fallback"
        detail["error_message"] = climatiq_result.error or fallback["message"]
        return detail


def pipeline(journal_entry: str) -> dict:
    return CarbonPipeline().run(journal_entry)
