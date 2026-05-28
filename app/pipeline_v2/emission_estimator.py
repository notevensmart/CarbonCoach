from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.domain.assumptions import DEFAULT_ELECTRICITY_REGION
from app.domain.models import CarbonEvent, EstimateStatus, FactorCandidate, Issue
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever, FactorRetriever
from app.pipeline_v2.validator import FactorCompatibilityValidator
from app.services.climatiq_api import ClimatiqClient


@dataclass(frozen=True)
class EmissionEstimateResult:
    ok: bool
    co2e: float | None = None
    co2e_unit: str = "kg"
    activity_id: str | None = None
    factor: FactorCandidate | None = None
    issues: list[Issue] = field(default_factory=list)
    failure_status: EstimateStatus = "failed"


class EmissionEstimator(Protocol):
    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        """Return an emission estimate whose factor originates from Climatiq."""


class ClimatiqEmissionEstimator:
    """Retrieves compatible Climatiq IDs, then estimates through Climatiq Basic Estimate."""

    def __init__(
        self,
        climatiq_client: ClimatiqClient | None = None,
        factor_retriever: FactorRetriever | None = None,
        activity_search: Callable[..., list[dict]] | None = None,
        factor_validator: FactorCompatibilityValidator | None = None,
    ) -> None:
        self.climatiq_client = climatiq_client or ClimatiqClient()
        self.factor_validator = factor_validator or FactorCompatibilityValidator()
        self.factor_retriever = factor_retriever or ClimatiqFactorRetriever(
            local_records_provider=(lambda: []) if activity_search is not None else None,
            remote_search=activity_search,
            validator=self.factor_validator,
        )

    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        try:
            candidates = self.factor_retriever.retrieve(event, parameters, limit=5)
        except Exception as exc:
            return EmissionEstimateResult(
                ok=False,
                failure_status="unresolved",
                issues=[
                    Issue(
                        code="climatiq.factor_retrieval_failed",
                        message=f"Could not retrieve a compatible Climatiq factor: {exc}",
                        severity="warning",
                    )
                ],
            )
        if not candidates:
            return EmissionEstimateResult(
                ok=False,
                failure_status="unresolved",
                issues=[
                    Issue(
                        code="climatiq.factor_unavailable",
                        message=(
                            f"No compatible Climatiq factor was found for "
                            f"{event.activity_type} and its parameter dimensions."
                        ),
                        severity="warning",
                    )
                ],
            )

        errors: list[str] = []
        attempted_estimate = False
        attempted_factor: FactorCandidate | None = None
        for candidate in candidates:
            validation = self.factor_validator.validate_candidate(event, parameters, candidate)
            if not validation.compatible:
                errors.extend(validation.errors)
                continue
            attempted_estimate = True
            attempted_factor = candidate
            try:
                result = self._estimate_candidate(event, parameters, candidate)
            except Exception as exc:
                errors.append(f"Climatiq request failed: {exc}")
                break
            if result.ok and result.co2e is not None:
                return EmissionEstimateResult(
                    ok=True,
                    co2e=round(float(result.co2e), 3),
                    co2e_unit=result.co2e_unit or "kg",
                    activity_id=candidate.activity_id,
                    factor=candidate,
                )
            if result.error:
                errors.append(result.error)
            break

        return EmissionEstimateResult(
            ok=False,
            activity_id=attempted_factor.activity_id if attempted_factor else None,
            factor=attempted_factor,
            failure_status="failed" if attempted_estimate else "unresolved",
            issues=[
                Issue(
                    code=(
                        "climatiq.estimate_failed"
                        if attempted_estimate
                        else "climatiq.factor_incompatible"
                    ),
                    message=errors[-1] if errors else "Climatiq could not estimate this activity.",
                    severity="warning",
                )
            ],
        )

    def _estimate_candidate(
        self,
        event: CarbonEvent,
        parameters: dict,
        candidate: FactorCandidate,
    ):
        api_parameters = _climatiq_parameters(parameters, candidate.unit_type)
        selector_filters = _selector_filters(event)
        if selector_filters:
            return self.climatiq_client.estimate(
                candidate.activity_id,
                api_parameters,
                selector_filters=selector_filters,
            )
        return self.climatiq_client.estimate(candidate.activity_id, api_parameters)


def _selector_filters(event: CarbonEvent) -> dict:
    if event.category == "energy":
        return {
            "region": DEFAULT_ELECTRICITY_REGION,
            "region_fallback": True,
        }
    return {}


def _climatiq_parameters(parameters: dict, unit_type: str) -> dict:
    if unit_type.lower() == "energy":
        return {
            "energy": parameters["energy"],
            "energy_unit": parameters["energy_unit"],
        }
    if unit_type.lower() == "number":
        return {
            "number": parameters["number"],
        }
    if unit_type.lower() == "weight":
        return {
            "weight": parameters["weight"],
            "weight_unit": parameters["weight_unit"],
        }
    api_parameters = {
        "distance": parameters["distance"],
        "distance_unit": parameters["distance_unit"],
    }
    if unit_type.lower() == "passengeroverdistance":
        api_parameters["passengers"] = int(parameters.get("passengers", 1))
    return api_parameters
