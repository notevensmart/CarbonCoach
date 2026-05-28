from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent
from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.hybrid_event_extractor import EmptyEventExtractor, HybridEventExtractor
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.llm_event_extractor import LLMStructuredEventExtractor
from app.pipeline_v2.pipeline import CarbonPipelineV2


@dataclass(frozen=True)
class ExtractionEvaluationReport:
    row_count: int
    expected_event_count: int
    heuristic_expected_matches: int
    hybrid_expected_matches: int
    heuristic_expected_recall: float
    hybrid_expected_recall: float
    false_positive_count: int
    duplicate_event_count: int
    ordering_correct_count: int
    ordering_case_count: int
    controlled_taxonomy_valid: bool
    heuristic_event_preservation_rate: float
    pipeline_survival_rate: float
    recommended_hybrid_recall_met: bool

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class FixtureLLMClient:
    def __init__(self, events: list[dict[str, Any]] | None = None, response: str | None = None) -> None:
        self.events = events or []
        self.response = response
        self.prompts: list[str] = []

    def extract_events_json(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.response is not None:
            return self.response
        return json.dumps({"events": self.events})


class _EvaluationEmissionEstimator:
    def estimate(self, event: CarbonEvent, parameters: dict) -> EmissionEstimateResult:
        return EmissionEstimateResult(
            ok=False,
            failure_status="unresolved",
        )


def evaluate_extraction_fixture(
    fixture_path: str | Path,
    *,
    recommended_recall: float = 0.90,
) -> ExtractionEvaluationReport:
    rows = _load_rows(fixture_path)
    preprocessor = JournalPreprocessor()

    expected_total = 0
    heuristic_matches = 0
    hybrid_matches = 0
    false_positive_count = 0
    duplicate_event_count = 0
    ordering_correct_count = 0
    ordering_case_count = 0
    taxonomy_valid = True
    preserved_total = 0
    preserved_matches = 0
    pipeline_survival_count = 0

    for row in rows:
        journal = preprocessor.preprocess(str(row["input"]))
        heuristic_extractor = JournalEventExtractor()
        heuristic_events = heuristic_extractor.extract(journal)
        hybrid_extractor = HybridEventExtractor(
            heuristic_extractor=JournalEventExtractor(),
            llm_extractor=LLMStructuredEventExtractor(
                FixtureLLMClient(events=list(row.get("llm_events", []))),
                EmptyEventExtractor(),
            ),
        )
        hybrid_events = hybrid_extractor.extract(journal)

        expected_events = list(row.get("expected_events", []))
        expected_total += len(expected_events)
        heuristic_matches += _matched_expected_count(heuristic_events, expected_events)
        hybrid_matches += _matched_expected_count(hybrid_events, expected_events)

        negative_activity_types = set(row.get("negative_activity_types", []))
        false_positive_count += sum(
            event.activity_type in negative_activity_types for event in hybrid_events
        )
        duplicate_event_count += _duplicate_count(hybrid_events)

        if expected_events:
            ordering_case_count += 1
            if _ordering_matches(hybrid_events, expected_events):
                ordering_correct_count += 1

        taxonomy_valid = taxonomy_valid and all(_taxonomy_is_valid(event) for event in hybrid_events)

        preserved_total += len(heuristic_events)
        preserved_matches += _preserved_heuristic_count(heuristic_events, hybrid_events)

        try:
            CarbonPipelineV2(
                event_extractor=hybrid_extractor,
                emission_estimator=_EvaluationEmissionEstimator(),
            ).run(str(row["input"]))
            pipeline_survival_count += 1
        except Exception:
            pass

    heuristic_recall = _ratio(heuristic_matches, expected_total)
    hybrid_recall = _ratio(hybrid_matches, expected_total)
    return ExtractionEvaluationReport(
        row_count=len(rows),
        expected_event_count=expected_total,
        heuristic_expected_matches=heuristic_matches,
        hybrid_expected_matches=hybrid_matches,
        heuristic_expected_recall=heuristic_recall,
        hybrid_expected_recall=hybrid_recall,
        false_positive_count=false_positive_count,
        duplicate_event_count=duplicate_event_count,
        ordering_correct_count=ordering_correct_count,
        ordering_case_count=ordering_case_count,
        controlled_taxonomy_valid=taxonomy_valid,
        heuristic_event_preservation_rate=_ratio(preserved_matches, preserved_total),
        pipeline_survival_rate=_ratio(pipeline_survival_count, len(rows)),
        recommended_hybrid_recall_met=hybrid_recall >= recommended_recall,
    )


def _load_rows(fixture_path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(fixture_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _matched_expected_count(
    events: list[CarbonEvent],
    expected_events: list[dict[str, Any]],
) -> int:
    actual = Counter((event.category, event.activity_type) for event in events)
    expected = Counter(
        (expected["category"], expected["activity_type"]) for expected in expected_events
    )
    return sum(min(actual[key], count) for key, count in expected.items())


def _duplicate_count(events: list[CarbonEvent]) -> int:
    seen: set[tuple[str, str, str]] = set()
    duplicates = 0
    for event in events:
        key = (event.category, event.activity_type, _normalized_text(event.raw_text))
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def _ordering_matches(
    events: list[CarbonEvent],
    expected_events: list[dict[str, Any]],
) -> bool:
    expected = [
        (expected["category"], expected["activity_type"]) for expected in expected_events
    ]
    actual = [(event.category, event.activity_type) for event in events]
    position = 0
    for key in actual:
        if position < len(expected) and key == expected[position]:
            position += 1
    return position == len(expected)


def _taxonomy_is_valid(event: CarbonEvent) -> bool:
    metadata = ACTIVITY_TAXONOMY.get(event.activity_type)
    return bool(metadata and metadata.get("category") == event.category)


def _preserved_heuristic_count(
    heuristic_events: list[CarbonEvent],
    hybrid_events: list[CarbonEvent],
) -> int:
    hybrid_counts = Counter(_preservation_key(event) for event in hybrid_events)
    preserved = 0
    for event in heuristic_events:
        key = _preservation_key(event)
        if hybrid_counts[key] > 0:
            preserved += 1
            hybrid_counts[key] -= 1
    return preserved


def _preservation_key(event: CarbonEvent) -> tuple[str, str, str]:
    return event.category, event.activity_type, _normalized_text(event.raw_text)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 3)


def _normalized_text(text: str) -> str:
    return " ".join(text.lower().strip(" ,.;").split())
