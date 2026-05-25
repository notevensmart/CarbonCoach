from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, Issue
from app.services.climatiq_api import ClimatiqClient, search_activity_ids


@dataclass(frozen=True)
class EmissionEstimateResult:
    ok: bool
    co2e: float | None = None
    co2e_unit: str = "kg"
    activity_id: str | None = None
    issues: list[Issue] = field(default_factory=list)


class EmissionEstimator(Protocol):
    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        """Return an emission estimate whose factor originates from Climatiq."""


class ClimatiqEmissionEstimator:
    """Selects and estimates a compatible Climatiq factor for a normalized V2 event."""

    def __init__(
        self,
        climatiq_client: ClimatiqClient | None = None,
        activity_search: Callable[[str, int], list[dict]] | None = None,
    ) -> None:
        self.climatiq_client = climatiq_client or ClimatiqClient()
        self.activity_search = activity_search or search_activity_ids

    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        query = _factor_query(event, parameters)
        candidates = self.activity_search(query, 5)
        required_unit_type = "energy" if event.category == "energy" else "distance"
        candidate = next(
            (
                item
                for item in candidates
                if str(item.get("unit_type", "")).strip().lower() == required_unit_type
                and item.get("activity_id")
            ),
            None,
        )
        if candidate is None:
            return EmissionEstimateResult(
                ok=False,
                issues=[
                    Issue(
                        code="climatiq.factor_unavailable",
                        message=(
                            f"No compatible Climatiq {required_unit_type} factor was found "
                            f"for {event.activity_type}."
                        ),
                        severity="warning",
                    )
                ],
            )

        result = self.climatiq_client.estimate(
            str(candidate["activity_id"]),
            _climatiq_parameters(event, parameters),
        )
        if not result.ok or result.co2e is None:
            return EmissionEstimateResult(
                ok=False,
                activity_id=str(candidate["activity_id"]),
                issues=[
                    Issue(
                        code="climatiq.estimate_failed",
                        message=result.error or "Climatiq could not estimate this activity.",
                        severity="warning",
                    )
                ],
            )
        return EmissionEstimateResult(
            ok=True,
            co2e=round(float(result.co2e), 3),
            co2e_unit=result.co2e_unit or "kg",
            activity_id=str(candidate["activity_id"]),
        )


def _factor_query(event: CarbonEvent, parameters: dict) -> str:
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    query = str(metadata.get("climatiq_factor_query", event.activity_type))
    traits = [
        str(parameters[key])
        for key in ("fuel_type", "vehicle_size", "vehicle_class")
        if parameters.get(key)
    ]
    return " ".join([query, *traits]).strip()


def _climatiq_parameters(event: CarbonEvent, parameters: dict) -> dict:
    if event.category == "energy":
        return {
            "energy": parameters["energy"],
            "energy_unit": parameters["energy_unit"],
        }
    return {
        "distance": parameters["distance"],
        "distance_unit": parameters["distance_unit"],
    }
