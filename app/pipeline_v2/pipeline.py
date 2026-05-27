from __future__ import annotations

from app.domain.models import (
    CarbonEstimateResponse,
    CarbonEvent,
    Confidence,
    EstimateDetail,
    EstimateTotal,
    SourceBreakdown,
)
from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator, EmissionEstimator
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.entity_enricher import EntityEnricher
from app.pipeline_v2.fallback_estimator import LocalFallbackEstimator
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.parameter_builders import (
    EnergyParameterBuilder,
    ParameterBuildResult,
    TransportParameterBuilder,
)
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer


class CarbonPipelineV2:
    def __init__(
        self,
        preprocessor: JournalPreprocessor | None = None,
        event_extractor: JournalEventExtractor | None = None,
        quantity_normalizer: QuantityNormalizer | None = None,
        entity_enricher: EntityEnricher | None = None,
        energy_builder: EnergyParameterBuilder | None = None,
        transport_builder: TransportParameterBuilder | None = None,
        emission_estimator: EmissionEstimator | None = None,
        fallback_estimator: LocalFallbackEstimator | None = None,
    ) -> None:
        self.preprocessor = preprocessor or JournalPreprocessor()
        self.event_extractor = event_extractor or JournalEventExtractor()
        self.quantity_normalizer = quantity_normalizer or QuantityNormalizer()
        self.entity_enricher = entity_enricher or EntityEnricher()
        self.energy_builder = energy_builder or EnergyParameterBuilder()
        self.transport_builder = transport_builder or TransportParameterBuilder()
        self.emission_estimator = emission_estimator or ClimatiqEmissionEstimator()
        self.fallback_estimator = fallback_estimator or LocalFallbackEstimator()

    def run(self, journal_entry: str) -> CarbonEstimateResponse:
        preprocessed = self.preprocessor.preprocess(journal_entry)
        extracted_events = self.event_extractor.extract(preprocessed)
        details = [self._estimate_event(self._normalize_event(event)) for event in extracted_events]

        total = _build_total(details)
        return CarbonEstimateResponse(total=total, details=details)

    def _estimate_event(self, event: CarbonEvent) -> EstimateDetail:
        metadata = ACTIVITY_TAXONOMY.get(event.activity_type, {})
        if metadata.get("estimate_policy") == "not_estimated":
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status="not_estimated",
                parameters={"emissions_boundary": metadata["emissions_boundary"]},
                co2e=0.0,
                source="none",
                confidence=event.confidence,
                parameter_confidence=event.confidence,
                assumptions=event.assumptions,
                issues=event.issues,
            )
        if event.category == "energy":
            return self._estimate_energy_event(event)
        if event.category == "transport":
            return self._estimate_transport_event(event)

        return EstimateDetail(
            raw_text=event.raw_text,
            category=event.category,
            activity_type=event.activity_type,
            status="unresolved",
            parameters={},
            source="unresolved",
            confidence=Confidence.from_score(0.20),
            assumptions=event.assumptions,
            issues=event.issues,
        )

    def _normalize_event(self, event: CarbonEvent) -> CarbonEvent:
        with_quantities = event.model_copy(
            update={"quantities": self.quantity_normalizer.normalize(event.raw_text, event)}
        )
        return self.entity_enricher.enrich(with_quantities)

    def _estimate_energy_event(self, event: CarbonEvent) -> EstimateDetail:
        build = self.energy_builder.build(event)
        return self._estimate_built_event(event, build)

    def _estimate_transport_event(self, event: CarbonEvent) -> EstimateDetail:
        build = self.transport_builder.build(event)
        return self._estimate_built_event(event, build)

    def _estimate_built_event(
        self,
        event: CarbonEvent,
        build: ParameterBuildResult,
    ) -> EstimateDetail:
        assumptions = [*event.assumptions, *build.assumptions]
        issues = [*event.issues, *build.issues]
        if build.status == "not_estimated":
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status="not_estimated",
                parameters=build.parameters,
                co2e=0.0,
                source="none",
                confidence=build.confidence,
                parameter_confidence=build.confidence,
                assumptions=assumptions,
                issues=issues,
            )
        if not build.can_estimate:
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status="unresolved",
                parameters=build.parameters,
                source="unresolved",
                confidence=build.confidence,
                parameter_confidence=build.confidence,
                assumptions=assumptions,
                issues=issues,
            )

        estimate = self.emission_estimator.estimate(event, build.parameters)
        parameters = dict(build.parameters)
        parameter_confidence = build.confidence
        if not estimate.ok or estimate.co2e is None:
            fallback = self.fallback_estimator.estimate(event, parameters)
            if fallback is not None:
                factor_confidence = Confidence.from_score(fallback.confidence)
                return EstimateDetail(
                    raw_text=event.raw_text,
                    category=event.category,
                    activity_type=event.activity_type,
                    status="fallback_estimated",
                    parameters=parameters,
                    co2e=fallback.co2e,
                    unit=fallback.co2e_unit,
                    source="fallback",
                    confidence=_overall_confidence(
                        parameter_confidence,
                        factor_confidence,
                        factor_confidence,
                    ),
                    parameter_confidence=parameter_confidence,
                    factor_confidence=factor_confidence,
                    source_confidence=factor_confidence,
                    assumptions=[*assumptions, *fallback.assumptions],
                    issues=[*issues, *estimate.issues],
                )
            failure_status = getattr(estimate, "failure_status", "failed")
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status=failure_status,
                parameters=parameters,
                source="unresolved" if failure_status == "unresolved" else "climatiq",
                confidence=parameter_confidence,
                parameter_confidence=parameter_confidence,
                factor_confidence=_factor_confidence(estimate.factor),
                assumptions=assumptions,
                issues=[*issues, *estimate.issues],
                factor=estimate.factor,
            )
        if estimate.factor and estimate.factor.specificity_match:
            assumptions, issues, parameters = _apply_specificity_match_visibility(
                event,
                assumptions,
                issues,
                parameters,
            )
            parameter_confidence = _specificity_match_confidence(event, parameter_confidence)
        factor_confidence = _factor_confidence(estimate.factor)
        source_confidence = Confidence.from_score(1.0)
        return EstimateDetail(
            raw_text=event.raw_text,
            category=event.category,
            activity_type=event.activity_type,
            status="estimated",
            parameters=parameters,
            co2e=estimate.co2e,
            unit=estimate.co2e_unit,
            source="climatiq",
            confidence=_overall_confidence(
                parameter_confidence,
                factor_confidence,
                source_confidence,
            ),
            parameter_confidence=parameter_confidence,
            factor_confidence=factor_confidence,
            source_confidence=source_confidence,
            assumptions=assumptions,
            issues=[*issues, *estimate.issues],
            factor=estimate.factor,
        )


def pipeline_v2(journal_entry: str) -> dict:
    return CarbonPipelineV2().run(journal_entry).model_dump(by_alias=True)


def _build_total(details: list[EstimateDetail]) -> EstimateTotal:
    breakdown = SourceBreakdown()
    total_co2e = 0.0
    weighted_confidence = 0.0
    confidence_weight = 0.0

    for detail in details:
        co2e = float(detail.co2e or 0.0)
        if detail.status == "estimated":
            breakdown.estimated = round(breakdown.estimated + co2e, 3)
        elif detail.status == "fallback_estimated":
            breakdown.fallback_estimated = round(breakdown.fallback_estimated + co2e, 3)
        elif detail.status == "not_estimated":
            breakdown.not_estimated = round(breakdown.not_estimated + co2e, 3)

        if detail.status in {"estimated", "fallback_estimated"}:
            total_co2e += co2e
            weighted_confidence += detail.confidence.score * max(co2e, 1.0)
            confidence_weight += max(co2e, 1.0)

    score = weighted_confidence / confidence_weight if confidence_weight else 0.0
    return EstimateTotal(
        co2e=round(total_co2e, 3),
        unit="kg",
        confidence=Confidence.from_score(score),
        source_breakdown=breakdown,
    )


def _apply_specificity_match_visibility(
    event: CarbonEvent,
    assumptions: list,
    issues: list,
    parameters: dict,
) -> tuple[list, list, dict]:
    if event.activity_type not in {"car_ride", "rideshare"}:
        return assumptions, issues, parameters
    parameters = dict(parameters)
    if event.entities.get("fuel_type_source") == "generic_default":
        parameters.pop("fuel_type", None)
    if event.entities.get("vehicle_size_source") == "generic_default":
        parameters.pop("vehicle_size", None)
    parameters["factor_specificity"] = "supplied_description"
    assumptions = [
        assumption
        for assumption in assumptions
        if assumption.code
        not in {
            "vehicle.named.default_petrol_medium",
            "vehicle.named.default_petrol",
            "vehicle.named.default_medium",
        }
    ]
    issues = [
        issue for issue in issues if issue.code != "vehicle.named_model.unmapped"
    ]
    return assumptions, issues, parameters


def _specificity_match_confidence(event: CarbonEvent, existing: Confidence) -> Confidence:
    if event.category != "transport":
        return existing
    distance = next(
        (quantity for quantity in event.quantities if quantity.dimension == "distance"),
        None,
    )
    if distance is None:
        return existing
    return Confidence.from_score(min(event.confidence.score, distance.confidence))


def _factor_confidence(factor) -> Confidence | None:
    if factor is None:
        return None
    return Confidence.from_score(factor.score)


def _overall_confidence(*confidence_parts: Confidence | None) -> Confidence:
    scores = [part.score for part in confidence_parts if part is not None]
    return Confidence.from_score(min(scores) if scores else 0.0)
