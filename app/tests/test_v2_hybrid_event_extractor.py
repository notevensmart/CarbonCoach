import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.extraction_evaluator import evaluate_extraction_fixture
from app.pipeline_v2.hybrid_event_extractor import EmptyEventExtractor, HybridEventExtractor
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.llm_event_extractor import (
    LLMStructuredEventExtractor,
    build_event_extractor,
)
from app.pipeline_v2.pipeline import CarbonPipelineV2


client = TestClient(app)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "v2_extraction_eval.jsonl"


class FakeLLMClient:
    def __init__(self, events=None, response=None, exc=None):
        self.events = events or []
        self.response = response
        self.exc = exc
        self.prompts = []

    def extract_events_json(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        if self.response is not None:
            return self.response
        return json.dumps({"events": self.events})


def test_build_event_extractor_enables_hybrid_only_with_injected_client(monkeypatch):
    monkeypatch.setenv("CARBONCOACH_V2_EXTRACTOR_MODE", "hybrid")

    assert isinstance(build_event_extractor(), JournalEventExtractor)
    assert isinstance(build_event_extractor(llm_client=FakeLLMClient()), HybridEventExtractor)


def test_hybrid_combines_heuristic_and_llm_events():
    events = _extract(
        "I drove 8 km home and picked up a flat white.",
        [{"raw_text": "picked up a flat white", "category": "goods_services", "activity_type": "coffee_purchase"}],
    )

    assert [event.activity_type for event in events] == ["car_ride", "coffee_purchase"]


def test_hybrid_adds_validated_llm_only_coffee_meal_waste_and_pc_events():
    events = _extract(
        "I picked up a flat white, picked up takeaway, disposed of cardboard, and worked on my PC for 2 hours.",
        [
            {"raw_text": "picked up a flat white", "category": "goods_services", "activity_type": "coffee_purchase"},
            {"raw_text": "picked up takeaway", "category": "goods_services", "activity_type": "restaurant_meal"},
            {"raw_text": "disposed of cardboard", "category": "waste", "activity_type": "landfill_waste"},
            {
                "raw_text": "worked on my PC for 2 hours",
                "category": "energy",
                "activity_type": "generic_energy_use",
                "quantities": [{"value": 2, "unit": "hours", "dimension": "duration", "surface": "2 hours"}],
                "entities": {"device": "PC"},
            },
        ],
    )

    assert [event.activity_type for event in events] == [
        "coffee_purchase",
        "restaurant_meal",
        "landfill_waste",
        "generic_energy_use",
    ]


def test_heuristic_events_survive_when_llm_misses_them():
    events = _extract("I drove 8 km home and ran the heater for 1 hour.", [])

    assert [event.activity_type for event in events] == ["car_ride", "space_heater_use"]


def test_heuristic_event_survives_same_span_llm_conflict():
    events = _extract(
        "I ordered takeaway through Uber Eats delivery app.",
        [{"raw_text": "Uber Eats", "category": "transport", "activity_type": "rideshare"}],
    )

    assert [event.activity_type for event in events] == ["restaurant_meal"]


def test_duplicate_heuristic_and_llm_events_collapse_to_one_detail(fake_climatiq_estimator):
    result = CarbonPipelineV2(
        event_extractor=_hybrid(
            [{"raw_text": "I bought two coffees.", "category": "goods_services", "activity_type": "coffee_purchase"}]
        ),
        emission_estimator=fake_climatiq_estimator,
    ).run("I bought two coffees.").model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == ["coffee_purchase"]
    assert result["details"][0]["parameters"]["number"] == 2


def test_adjacent_distinct_events_are_not_collapsed():
    events = _extract(
        "I grabbed a coffee and recycled the cup.",
        [{"raw_text": "recycled the cup", "category": "waste", "activity_type": "recycling"}],
    )

    assert [event.activity_type for event in events] == ["coffee_purchase", "recycling"]


def test_conflicting_llm_quantity_does_not_override_deterministic_quantity(fake_climatiq_estimator):
    result = CarbonPipelineV2(
        event_extractor=_hybrid(
            [
                {
                    "raw_text": "I recycled 1 kg of cardboard.",
                    "category": "waste",
                    "activity_type": "recycling",
                    "quantities": [{"value": 2, "unit": "kg", "dimension": "weight", "surface": "2 kg"}],
                    "entities": {"material": "cardboard"},
                }
            ]
        ),
        emission_estimator=fake_climatiq_estimator,
    ).run("I recycled 1 kg of cardboard.").model_dump()

    assert result["details"][0]["parameters"]["weight"] == 1.0


def test_same_span_category_activity_conflict_preserves_deterministic_event():
    events = _extract(
        "I ordered takeaway through a delivery app.",
        [{"raw_text": "delivery app", "category": "transport", "activity_type": "rideshare"}],
    )

    assert [event.activity_type for event in events] == ["restaurant_meal"]


def test_invalid_llm_category_or_activity_is_rejected():
    events = _extract(
        "I picked up a flat white.",
        [{"raw_text": "picked up a flat white", "category": "energy", "activity_type": "coffee_purchase"}],
    )

    assert events == []


def test_unsupported_appliance_names_do_not_create_invented_activity_types():
    events = _extract(
        "I ran the dryer for 1 hour and ran laundry for 45 minutes.",
        [
            {"raw_text": "ran the dryer for 1 hour", "category": "energy", "activity_type": "dryer_use"},
            {
                "raw_text": "ran laundry for 45 minutes",
                "category": "energy",
                "activity_type": "generic_energy_use",
                "entities": {"device": "laundry appliance"},
            },
        ],
    )

    assert [event.activity_type for event in events] == ["generic_energy_use"]
    assert all(event.activity_type in ACTIVITY_TAXONOMY for event in events)


def test_raw_span_ordering_controls_detail_order():
    events = _extract(
        "I picked up a flat white then drove 8 km home.",
        [{"raw_text": "picked up a flat white", "category": "goods_services", "activity_type": "coffee_purchase"}],
    )

    assert [event.activity_type for event in events] == ["coffee_purchase", "car_ride"]


def test_evaluation_harness_reports_recall_improvement_over_heuristic_only():
    report = evaluate_extraction_fixture(FIXTURE_PATH)

    assert report.hybrid_expected_recall > report.heuristic_expected_recall
    assert report.hybrid_expected_recall >= 0.90
    assert report.recommended_hybrid_recall_met is True
    assert report.heuristic_event_preservation_rate == 1.0


def test_negative_examples_produce_zero_false_positives():
    report = evaluate_extraction_fixture(FIXTURE_PATH)

    assert report.false_positive_count == 0
    assert report.duplicate_event_count == 0
    assert report.controlled_taxonomy_valid is True


def test_representative_mixed_journal_has_improved_represented_coverage(fake_climatiq_estimator):
    journal = "I drove 8 km home and worked on my PC for 2 hours."
    heuristic = CarbonPipelineV2(emission_estimator=fake_climatiq_estimator).run(journal)
    hybrid = CarbonPipelineV2(
        event_extractor=_hybrid(
            [
                {
                    "raw_text": "worked on my PC for 2 hours",
                    "category": "energy",
                    "activity_type": "generic_energy_use",
                    "quantities": [{"value": 2, "unit": "hours", "dimension": "duration", "surface": "2 hours"}],
                    "entities": {"device": "PC"},
                }
            ]
        ),
        emission_estimator=fake_climatiq_estimator,
    ).run(journal)

    assert len(hybrid.details) > len(heuristic.details)
    assert hybrid.coverage.represented_activity_count == 2
    assert hybrid.coverage.unresolved_count == 1
    assert hybrid.comparison is None


def test_hybrid_provider_failure_falls_back_to_heuristic_only():
    events = HybridEventExtractor(
        heuristic_extractor=JournalEventExtractor(),
        llm_extractor=LLMStructuredEventExtractor(
            FakeLLMClient(exc=TimeoutError("timed out")),
            EmptyEventExtractor(),
        ),
    ).extract(JournalPreprocessor().preprocess("I drove 8 km home."))

    assert [event.activity_type for event in events] == ["car_ride"]


def test_hybrid_does_not_change_existing_transport_co2e(fake_climatiq_estimator):
    journal = "I drove 8 km home."
    heuristic = CarbonPipelineV2(emission_estimator=fake_climatiq_estimator).run(journal)
    hybrid = CarbonPipelineV2(
        event_extractor=_hybrid(
            [{"raw_text": "I drove 8 km home.", "category": "transport", "activity_type": "car_ride"}]
        ),
        emission_estimator=fake_climatiq_estimator,
    ).run(journal)

    assert hybrid.total.co2e == heuristic.total.co2e
    assert len(hybrid.details) == 1


def test_estimate_v2_api_remains_valid_with_hybrid_mode_and_fake_candidates(
    monkeypatch,
    fake_climatiq_estimator,
):
    app_module.is_ready = True
    app_module.preload_error = None
    pipeline = CarbonPipelineV2(
        extractor_mode="hybrid",
        llm_client=FakeLLMClient(
            events=[
                {"raw_text": "picked up a flat white", "category": "goods_services", "activity_type": "coffee_purchase"}
            ]
        ),
        emission_estimator=fake_climatiq_estimator,
    )
    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: pipeline.run(journal).model_dump(by_alias=True),
    )

    response = client.post(
        "/api/estimate-v2",
        json={"journal": "I drove 8 km home and picked up a flat white."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v2"
    assert [detail["activity_type"] for detail in data["details"]] == [
        "car_ride",
        "coffee_purchase",
    ]


def test_v1_estimate_still_works_after_hybrid_changes(monkeypatch):
    app_module.is_ready = True
    app_module.preload_error = None
    monkeypatch.setattr(
        app_module,
        "pipeline",
        lambda journal: {"result": {"co2e": 1.0, "unit": "kg", "details": []}},
    )

    response = client.post("/api/estimate", json={"journal": "legacy estimate"})

    assert response.status_code == 200
    assert response.json()["result"]["co2e"] == 1.0


def _extract(journal_text, llm_events):
    return _hybrid(llm_events).extract(JournalPreprocessor().preprocess(journal_text))


def _hybrid(llm_events):
    return HybridEventExtractor(
        heuristic_extractor=JournalEventExtractor(),
        llm_extractor=LLMStructuredEventExtractor(
            FakeLLMClient(events=llm_events),
            EmptyEventExtractor(),
        ),
    )
