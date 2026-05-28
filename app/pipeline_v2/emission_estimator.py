from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.domain.assumptions import DEFAULT_ELECTRICITY_REGION
from app.domain.factor_intents import FactorIntent
from app.domain.models import Assumption, CarbonEvent, EstimateStatus, FactorCandidate, Issue
from app.pipeline_v2.calculation_intent_resolver import CalculationIntentResolver
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever, FactorRetriever
from app.pipeline_v2.retrieval_diagnostics import (
    combine_attempt_diagnostics,
    empty_factor_diagnostics,
    with_fallback,
    with_selected_candidate,
)
from app.pipeline_v2.validator import FactorCompatibilityValidator
from app.services.climatiq_api import ClimatiqClient


@dataclass(frozen=True)
class EmissionEstimateResult:
    ok: bool
    co2e: float | None = None
    co2e_unit: str = "kg"
    activity_id: str | None = None
    factor: FactorCandidate | None = None
    factor_diagnostics: dict | None = None
    assumptions: list[Assumption] = field(default_factory=list)
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
        intent_resolver: CalculationIntentResolver | None = None,
    ) -> None:
        self.climatiq_client = climatiq_client or ClimatiqClient()
        self.factor_validator = factor_validator or FactorCompatibilityValidator()
        self.intent_resolver = intent_resolver or CalculationIntentResolver()
        self.factor_retriever = factor_retriever or ClimatiqFactorRetriever(
            local_records_provider=(lambda: []) if activity_search is not None else None,
            remote_search=activity_search,
            validator=self.factor_validator,
        )

    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        intents = self.intent_resolver.resolve(event, parameters)
        if not intents:
            diagnostics = empty_factor_diagnostics(None, "")
            return EmissionEstimateResult(
                ok=False,
                failure_status="unresolved",
                factor_diagnostics=diagnostics,
                issues=[
                    Issue(
                        code="calculation_intent.unavailable",
                        message=(
                            f"No estimable factor intent could be built for "
                            f"{event.activity_type} and its normalized parameters."
                        ),
                        severity="warning",
                    )
                ],
            )

        all_diagnostics: list[dict] = []
        errors: list[str] = []
        attempted_estimate = False
        attempted_factor: FactorCandidate | None = None
        found_candidates = False
        for intent in intents:
            try:
                candidates, diagnostics = self._retrieve_candidates(event, parameters, intent)
            except Exception as exc:
                return EmissionEstimateResult(
                    ok=False,
                    failure_status="unresolved",
                    factor_diagnostics=combine_attempt_diagnostics(all_diagnostics),
                    issues=[
                        Issue(
                            code="climatiq.factor_retrieval_failed",
                            message=f"Could not retrieve a compatible Climatiq factor: {exc}",
                            severity="warning",
                        )
                    ],
                )
            all_diagnostics.append(diagnostics)
            if not candidates:
                continue
            found_candidates = True
            for candidate in candidates:
                validation = self.factor_validator.validate_candidate(
                    event,
                    parameters,
                    candidate,
                    intent=intent,
                )
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
                selected_diagnostics = with_selected_candidate(
                    combine_attempt_diagnostics(all_diagnostics),
                    candidate,
                )
                selected_assumptions: list[Assumption] = []
                if intent.assumption_if_generic_fallback_used is not None:
                    selected_assumptions.append(intent.assumption_if_generic_fallback_used)
                    selected_diagnostics = with_fallback(
                        selected_diagnostics,
                        reason=(
                            "Selected a compatible broader generic factor after "
                            "the more specific intent did not produce a usable factor."
                        ),
                        assumption_code=intent.assumption_if_generic_fallback_used.code,
                    )
                if result.ok and result.co2e is not None:
                    return EmissionEstimateResult(
                        ok=True,
                        co2e=round(float(result.co2e), 3),
                        co2e_unit=result.co2e_unit or "kg",
                        activity_id=candidate.activity_id,
                        factor=candidate,
                        factor_diagnostics=selected_diagnostics,
                        assumptions=selected_assumptions,
                    )
                if result.error:
                    errors.append(result.error)
                break
            if attempted_estimate:
                break

        if not found_candidates:
            return EmissionEstimateResult(
                ok=False,
                failure_status="unresolved",
                factor_diagnostics=combine_attempt_diagnostics(all_diagnostics),
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

        return EmissionEstimateResult(
            ok=False,
            activity_id=attempted_factor.activity_id if attempted_factor else None,
            factor=attempted_factor,
            factor_diagnostics=combine_attempt_diagnostics(all_diagnostics),
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

    def _retrieve_candidates(
        self,
        event: CarbonEvent,
        parameters: dict,
        intent: FactorIntent,
    ) -> tuple[list[FactorCandidate], dict]:
        retriever_with_diagnostics = getattr(
            self.factor_retriever,
            "retrieve_with_diagnostics",
            None,
        )
        if callable(retriever_with_diagnostics):
            result = retriever_with_diagnostics(
                event,
                parameters,
                limit=5,
                intent=intent,
            )
            return result.candidates, result.diagnostics
        try:
            candidates = self.factor_retriever.retrieve(
                event,
                parameters,
                limit=5,
                intent=intent,
            )
        except TypeError:
            candidates = self.factor_retriever.retrieve(event, parameters, limit=5)
        diagnostics = empty_factor_diagnostics(intent, intent.search_query)
        diagnostics.update(
            {
                "candidate_count": len(candidates),
                "selected_activity_id": candidates[0].activity_id if candidates else None,
                "selected_reason": (
                    "; ".join(candidates[0].match_reasons[:4]) if candidates else None
                ),
            }
        )
        return candidates, diagnostics

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
    if unit_type.lower() == "money":
        return {
            "money": parameters["money"],
            "money_unit": parameters["money_unit"],
        }
    api_parameters = {
        "distance": parameters["distance"],
        "distance_unit": parameters["distance_unit"],
    }
    if unit_type.lower() == "passengeroverdistance":
        api_parameters["passengers"] = int(parameters.get("passengers", 1))
    return api_parameters
