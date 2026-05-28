from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, PreprocessedJournal
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.extractor_protocol import EventExtractor
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer


PROVENANCE_EXTRACTOR_SOURCE = "extractor_source"
PROVENANCE_MERGED_FROM = "merged_from"
PROVENANCE_LLM_CANDIDATE_INDEX = "llm_candidate_index"

_DOMINANT_ENTITY_FIELDS = (
    "product_class",
    "item",
    "material_class",
    "material",
    "device",
    "transport_mode",
    "vehicle_type",
    "vehicle_description",
    "disposal_method",
)


@dataclass(frozen=True)
class _PositionedEvent:
    event: CarbonEvent
    source: str
    index: int
    span: tuple[int, int] | None


class HybridEventExtractor:
    """Merge deterministic events with validated LLM candidate events.

    The LLM extractor used here must already validate candidates into
    CarbonEvent objects. This class keeps the deterministic extractor
    authoritative for quantities, conflicts, confidence, and final ordering.
    """

    def __init__(
        self,
        heuristic_extractor: EventExtractor | None = None,
        llm_extractor: EventExtractor | None = None,
        quantity_normalizer: QuantityNormalizer | None = None,
    ) -> None:
        self.heuristic_extractor = heuristic_extractor or JournalEventExtractor()
        self.llm_extractor = llm_extractor
        self.quantity_normalizer = quantity_normalizer or QuantityNormalizer()

    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        heuristic_events = self.heuristic_extractor.extract(journal)
        heuristic_positioned = [
            _PositionedEvent(
                event=_with_provenance(event, extractor_source="heuristic"),
                source="heuristic",
                index=index,
                span=_find_span(journal, event.raw_text),
            )
            for index, event in enumerate(heuristic_events)
        ]
        if self.llm_extractor is None:
            return [positioned.event for positioned in heuristic_positioned]

        try:
            llm_events = self.llm_extractor.extract(journal)
        except Exception:
            return [positioned.event for positioned in heuristic_positioned]

        accepted = list(heuristic_positioned)
        llm_only: list[_PositionedEvent] = []
        for index, llm_event in enumerate(llm_events):
            if not _taxonomy_is_valid(llm_event):
                continue
            candidate = _PositionedEvent(
                event=_with_provenance(
                    llm_event,
                    extractor_source="llm",
                    llm_candidate_index=index,
                ),
                source="llm",
                index=index,
                span=_find_span(journal, llm_event.raw_text),
            )
            merge_index = self._duplicate_heuristic_index(candidate, accepted)
            if merge_index is not None:
                accepted[merge_index] = _PositionedEvent(
                    event=_with_provenance(
                        accepted[merge_index].event,
                        extractor_source="hybrid",
                        merged_from="heuristic+llm",
                    ),
                    source=accepted[merge_index].source,
                    index=accepted[merge_index].index,
                    span=candidate.span or accepted[merge_index].span,
                )
                continue
            if self._conflicts_with_heuristic(candidate, accepted, journal):
                continue
            accepted.append(candidate)
            llm_only.append(candidate)

        if all(positioned.span is not None for positioned in accepted):
            return [
                positioned.event
                for positioned in sorted(
                    accepted,
                    key=lambda positioned: (
                        positioned.span[0] if positioned.span else 0,
                        0 if positioned.source == "heuristic" else 1,
                        positioned.index,
                    ),
                )
            ]
        return [positioned.event for positioned in heuristic_positioned] + [
            positioned.event for positioned in llm_only
        ]

    def _duplicate_heuristic_index(
        self,
        candidate: _PositionedEvent,
        existing: list[_PositionedEvent],
    ) -> int | None:
        for index, positioned in enumerate(existing):
            if positioned.source != "heuristic":
                continue
            if _same_calculation_boundary(
                positioned,
                candidate,
                self.quantity_normalizer,
            ):
                return index
        return None

    def _conflicts_with_heuristic(
        self,
        candidate: _PositionedEvent,
        existing: list[_PositionedEvent],
        journal: PreprocessedJournal,
    ) -> bool:
        for positioned in existing:
            if positioned.source != "heuristic":
                continue
            if not _same_span_or_overlap(positioned, candidate):
                continue
            if _has_activity_boundary_between(positioned, candidate, journal):
                continue
            if (
                positioned.event.category != candidate.event.category
                or positioned.event.activity_type != candidate.event.activity_type
            ):
                return True
        return False


class EmptyEventExtractor:
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        return []


def _same_calculation_boundary(
    heuristic: _PositionedEvent,
    candidate: _PositionedEvent,
    quantity_normalizer: QuantityNormalizer,
) -> bool:
    if heuristic.event.category != candidate.event.category:
        return False
    if heuristic.event.activity_type != candidate.event.activity_type:
        return False
    if not _same_span_or_overlap(heuristic, candidate):
        return False

    if _dominant_entities_conflict(heuristic.event, candidate.event):
        return False

    heuristic_quantities = _required_quantity_surfaces(
        heuristic.event,
        quantity_normalizer,
    )
    candidate_quantities = _required_quantity_surfaces(
        candidate.event,
        quantity_normalizer,
    )
    if heuristic_quantities and candidate_quantities:
        return bool(heuristic_quantities & candidate_quantities)
    return True


def _same_span_or_overlap(
    first: _PositionedEvent,
    second: _PositionedEvent,
) -> bool:
    if _normalized_text(first.event.raw_text) == _normalized_text(second.event.raw_text):
        return True
    if first.span is None or second.span is None:
        return False
    return first.span[0] < second.span[1] and second.span[0] < first.span[1]


def _has_activity_boundary_between(
    first: _PositionedEvent,
    second: _PositionedEvent,
    journal: PreprocessedJournal,
) -> bool:
    if first.span is None or second.span is None:
        return False
    contained_boundary = _contained_activity_boundary(first, second, journal)
    if contained_boundary is not None:
        return contained_boundary
    if first.span[0] <= second.span[0]:
        between = journal.raw_journal[first.span[0] : second.span[0]]
    else:
        between = journal.raw_journal[second.span[0] : first.span[0]]
    return bool(
        re.search(
            r"\b(?:and|then|after|before|later|while)\b\s*$",
            between,
            re.IGNORECASE,
        )
    )


def _contained_activity_boundary(
    first: _PositionedEvent,
    second: _PositionedEvent,
    journal: PreprocessedJournal,
) -> bool | None:
    if first.span is None or second.span is None:
        return None
    if _contains_span(first.span, second.span):
        outer, inner = first.span, second.span
    elif _contains_span(second.span, first.span):
        outer, inner = second.span, first.span
    else:
        return None

    before = journal.raw_journal[outer[0] : inner[0]]
    after = journal.raw_journal[inner[1] : outer[1]]
    return bool(
        re.search(r"\b(?:and|then|after|before|later|while)\b\s*$", before, re.I)
        or re.search(r"^\s*\b(?:and|then|after|before|later|while)\b", after, re.I)
    )


def _contains_span(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _required_quantity_surfaces(
    event: CarbonEvent,
    quantity_normalizer: QuantityNormalizer,
) -> set[str]:
    required = set(ACTIVITY_TAXONOMY.get(event.activity_type, {}).get("required_quantity_dimensions", ()))
    if not required:
        return set()
    normalized = quantity_normalizer.normalize(event.raw_text, event)
    return {
        _normalized_text(quantity.surface or "")
        for quantity in normalized
        if quantity.dimension in required and quantity.surface
    }


def _dominant_entities_conflict(first: CarbonEvent, second: CarbonEvent) -> bool:
    for field in _DOMINANT_ENTITY_FIELDS:
        first_value = first.entities.get(field)
        second_value = second.entities.get(field)
        if not isinstance(first_value, str) or not isinstance(second_value, str):
            continue
        if first_value.strip() and second_value.strip():
            if _normalized_text(first_value) != _normalized_text(second_value):
                return True
    return False


def _taxonomy_is_valid(event: CarbonEvent) -> bool:
    metadata = ACTIVITY_TAXONOMY.get(event.activity_type)
    return bool(metadata and metadata.get("category") == event.category)


def _with_provenance(
    event: CarbonEvent,
    *,
    extractor_source: str,
    merged_from: str | None = None,
    llm_candidate_index: int | None = None,
) -> CarbonEvent:
    entities = dict(event.entities)
    entities[PROVENANCE_EXTRACTOR_SOURCE] = extractor_source
    if merged_from:
        entities[PROVENANCE_MERGED_FROM] = merged_from
    if llm_candidate_index is not None:
        entities[PROVENANCE_LLM_CANDIDATE_INDEX] = llm_candidate_index
    return event.model_copy(update={"entities": entities})


def _find_span(
    journal: PreprocessedJournal,
    raw_text: str,
) -> tuple[int, int] | None:
    if not raw_text.strip():
        return None
    for source in (journal.raw_journal, journal.cleaned_journal):
        match = re.search(re.escape(raw_text.strip()), source, re.IGNORECASE)
        if match:
            return match.span()
    return _find_normalized_span(journal.raw_journal, raw_text) or _find_normalized_span(
        journal.cleaned_journal,
        raw_text,
    )


def _find_normalized_span(source: str, fragment: str) -> tuple[int, int] | None:
    normalized_fragment = _normalized_text(fragment)
    if not normalized_fragment:
        return None
    normalized_source = _normalized_text(source)
    start = normalized_source.find(normalized_fragment)
    if start < 0:
        return None
    return start, start + len(normalized_fragment)


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \t\r\n,.;").lower()
