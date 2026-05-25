from __future__ import annotations

from app.domain.assumptions import AU_ELECTRICITY_FALLBACK_KG_CO2E_PER_KWH
from app.domain.models import (
    CarbonEstimateResponse,
    CarbonEvent,
    Confidence,
    EstimateDetail,
    EstimateTotal,
    SourceBreakdown,
)
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.entity_enricher import EntityEnricher
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.parameter_builders import EnergyParameterBuilder, TransportParameterBuilder
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
    ) -> None:
        self.preprocessor = preprocessor or JournalPreprocessor()
        self.event_extractor = event_extractor or JournalEventExtractor()
        self.quantity_normalizer = quantity_normalizer or QuantityNormalizer()
        self.entity_enricher = entity_enricher or EntityEnricher()
        self.energy_builder = energy_builder or EnergyParameterBuilder()
        self.transport_builder = transport_builder or TransportParameterBuilder()

    def run(self, journal_entry: str) -> CarbonEstimateResponse:
        preprocessed = self.preprocessor.preprocess(journal_entry)
        extracted_events = self.event_extractor.extract(preprocessed)
        details = [self._estimate_event(self._normalize_event(event)) for event in extracted_events]

        total = _build_total(details)
        return CarbonEstimateResponse(total=total, details=details)

    def _estimate_event(self, event: CarbonEvent) -> EstimateDetail:
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
        if not build.can_estimate:
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status="unresolved",
                parameters=build.parameters,
                source="unresolved",
                confidence=build.confidence,
                assumptions=[*event.assumptions, *build.assumptions],
                issues=[*event.issues, *build.issues],
            )

        co2e = round(
            float(build.parameters["energy"]) * AU_ELECTRICITY_FALLBACK_KG_CO2E_PER_KWH,
            3,
        )
        return EstimateDetail(
            raw_text=event.raw_text,
            category=event.category,
            activity_type=event.activity_type,
            status="fallback_estimated",
            parameters=build.parameters,
            co2e=co2e,
            unit="kg",
            source="fallback",
            confidence=build.confidence,
            assumptions=[*event.assumptions, *build.assumptions],
            issues=[*event.issues, *build.issues],
        )

    def _estimate_transport_event(self, event: CarbonEvent) -> EstimateDetail:
        build = self.transport_builder.build(event)
        if not build.can_estimate:
            return EstimateDetail(
                raw_text=event.raw_text,
                category=event.category,
                activity_type=event.activity_type,
                status="unresolved",
                parameters=build.parameters,
                source="unresolved",
                confidence=build.confidence,
                assumptions=[*event.assumptions, *build.assumptions],
                issues=[*event.issues, *build.issues],
            )

        co2e = round(
            float(build.parameters["distance"]) * float(build.fallback_factor or 0.0),
            3,
        )
        return EstimateDetail(
            raw_text=event.raw_text,
            category=event.category,
            activity_type=event.activity_type,
            status="fallback_estimated",
            parameters=build.parameters,
            co2e=co2e,
            unit="kg",
            source="fallback",
            confidence=build.confidence,
            assumptions=[*event.assumptions, *build.assumptions],
            issues=[*event.issues, *build.issues],
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
