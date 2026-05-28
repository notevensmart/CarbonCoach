import json
import socket

import pytest
from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.domain.models import CarbonEvent, Confidence
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.extraction_schema import parse_llm_events_json
from app.pipeline_v2.extractor_protocol import EventExtractor
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.llm_event_extractor import (
    LLMStructuredEventExtractor,
    build_extraction_prompt,
)
from app.pipeline_v2.pipeline import CarbonPipelineV2


client = TestClient(app)


class FakeLLMClient:
    def __init__(self, response="", exc=None):
        self.response = response
        self.exc = exc
        self.prompts = []

    def extract_events_json(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        return self.response


class FallbackExtractor:
    def __init__(self, events=None):
        self.events = events or [_event("fallback heater", "energy", "space_heater_use")]
        self.calls = 0

    def extract(self, journal):
        self.calls += 1
        return self.events


def test_deterministic_extractor_satisfies_event_extractor_protocol():
    assert isinstance(JournalEventExtractor(), EventExtractor)


def test_prompt_contains_ticket_8_safety_instructions():
    journal = JournalPreprocessor().preprocess("I grabbed a coffee and took out rubbish.")
    prompt = build_extraction_prompt(journal)

    assert "Return JSON only" in prompt
    assert "Allowed categories: transport, energy, waste, goods_services" in prompt
    assert "Use goods_services for food, coffee, meals" in prompt
    assert "Use waste only when disposal" in prompt
    assert "Never invent distance, weight, money, power, duration, or mass" in prompt
    assert "Return candidate events, not final emissions estimates" in prompt


def test_valid_multi_event_llm_json_becomes_validated_carbon_events():
    journal = JournalPreprocessor().preprocess(
        "I bought two coffees, ran the heater for 3 hours, and recycled 500 g of plastic bottles."
    )
    payload = _json(
        [
            {
                "raw_text": "bought two coffees",
                "category": "goods_services",
                "activity_type": "coffee_purchase",
                "quantities": [
                    {
                        "value": 2,
                        "unit": "item",
                        "dimension": "number",
                        "surface": "two coffees",
                        "evidence": "explicit",
                    }
                ],
                "entities": {"item": "coffee"},
            },
            {
                "raw_text": "ran the heater for 3 hours",
                "category": "energy",
                "activity_type": "space_heater_use",
                "quantities": [
                    {
                        "value": 3,
                        "unit": "hours",
                        "dimension": "duration",
                        "surface": "3 hours",
                    }
                ],
                "entities": {"device": "heater"},
            },
            {
                "raw_text": "recycled 500 g of plastic bottles",
                "category": "waste",
                "activity_type": "recycling",
                "quantities": [
                    {
                        "value": 500,
                        "unit": "g",
                        "dimension": "weight",
                        "surface": "500 g",
                    }
                ],
                "entities": {"material": "plastic"},
            },
        ]
    )

    events = LLMStructuredEventExtractor(FakeLLMClient(payload)).extract(journal)

    assert [event.activity_type for event in events] == [
        "coffee_purchase",
        "space_heater_use",
        "recycling",
    ]
    assert events[0].entities["product_class"] == "coffee"
    assert events[0].quantities[0].value == 2
    assert events[1].quantities[0].dimension == "duration"
    assert events[2].quantities[0].value == 0.5
    assert events[2].entities["disposal_method"] == "recycling"
    assert all(event.confidence.score == 0.75 for event in events)


@pytest.mark.parametrize(
    "response",
    [
        "not-json",
        "",
        "   ",
    ],
)
def test_malformed_or_empty_llm_output_falls_back_safely(response):
    fallback = FallbackExtractor()
    extractor = LLMStructuredEventExtractor(FakeLLMClient(response), fallback)

    events = extractor.extract(JournalPreprocessor().preprocess("I used the heater."))

    assert events == fallback.events
    assert fallback.calls == 1


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("provider unavailable"),
        TimeoutError("timed out"),
        socket.timeout("timed out"),
    ],
)
def test_provider_exception_or_timeout_falls_back_safely(exc):
    fallback = FallbackExtractor()
    extractor = LLMStructuredEventExtractor(FakeLLMClient(exc=exc), fallback)

    events = extractor.extract(JournalPreprocessor().preprocess("I used the heater."))

    assert events == fallback.events
    assert fallback.calls == 1


def test_invalid_category_activity_and_mismatch_are_rejected():
    journal = JournalPreprocessor().preprocess("I grabbed a coffee.")

    assert parse_llm_events_json(
        _json([
            {
                "raw_text": "grabbed a coffee",
                "category": "food",
                "activity_type": "coffee_purchase",
                "entities": {"item": "coffee"},
            }
        ]),
        journal,
    ) == []
    assert parse_llm_events_json(
        _json([
            {
                "raw_text": "grabbed a coffee",
                "category": "goods_services",
                "activity_type": "espresso_magic",
                "entities": {"item": "coffee"},
            }
        ]),
        journal,
    ) == []
    assert parse_llm_events_json(
        _json([
            {
                "raw_text": "grabbed a coffee",
                "category": "energy",
                "activity_type": "coffee_purchase",
                "entities": {"item": "coffee"},
            }
        ]),
        journal,
    ) == []


def test_raw_span_not_present_is_rejected_and_triggers_fallback():
    fallback = FallbackExtractor()
    extractor = LLMStructuredEventExtractor(
        FakeLLMClient(
            _json([
                {
                    "raw_text": "flew to Europe",
                    "category": "transport",
                    "activity_type": "flight",
                    "entities": {},
                }
            ])
        ),
        fallback,
    )

    events = extractor.extract(JournalPreprocessor().preprocess("I grabbed a coffee."))

    assert events == fallback.events
    assert fallback.calls == 1


def test_llm_injected_final_estimate_fields_are_ignored():
    journal = JournalPreprocessor().preprocess("I grabbed a takeaway coffee.")
    events = parse_llm_events_json(
        _json([
            {
                "raw_text": "grabbed a takeaway coffee",
                "category": "goods_services",
                "activity_type": "coffee_purchase",
                "co2e": 999,
                "activity_id": "malicious.factor",
                "confidence": 1.0,
                "assumptions": [{"code": "fake.assumption"}],
                "issues": [{"code": "fake.issue"}],
                "factor_metadata": {"unit_type": "Number"},
                "entities": {
                    "item": "coffee",
                    "activity_id": "malicious.factor",
                    "confidence": 1.0,
                },
            }
        ]),
        journal,
    )

    assert len(events) == 1
    event = events[0]
    assert event.confidence.score == 0.75
    assert event.assumptions == []
    assert event.issues == []
    assert "activity_id" not in event.entities
    assert "co2e" not in event.entities
    assert event.entities["product_class"] == "coffee"


def test_explicit_quantity_from_raw_text_is_preserved_with_deterministic_normalization():
    journal = JournalPreprocessor().preprocess("I bought two coffees.")
    events = parse_llm_events_json(
        _json([
            {
                "raw_text": "bought two coffees",
                "category": "goods_services",
                "activity_type": "coffee_purchase",
                "quantities": [
                    {
                        "value": 42,
                        "unit": "item",
                        "dimension": "number",
                        "surface": "two coffees",
                    }
                ],
                "entities": {"item": "coffee"},
            }
        ]),
        journal,
    )

    assert events[0].quantities[0].value == 2
    assert events[0].quantities[0].unit == "item"


def test_unsupported_inferred_quantity_is_not_accepted_as_explicit_evidence():
    journal = JournalPreprocessor().preprocess("I took out a bag of rubbish.")
    events = parse_llm_events_json(
        _json([
            {
                "raw_text": "took out a bag of rubbish",
                "category": "waste",
                "activity_type": "landfill_waste",
                "quantities": [
                    {
                        "value": 1,
                        "unit": "kg",
                        "dimension": "weight",
                        "surface": "bag of rubbish",
                        "evidence": "inferred",
                    }
                ],
                "entities": {"material_class": "general_waste"},
            }
        ]),
        journal,
    )

    assert len(events) == 1
    assert events[0].quantities == []


def test_singular_coffee_count_inference_comes_from_deterministic_rule(fake_climatiq_estimator):
    payload = _json([
        {
            "raw_text": "grabbed a takeaway coffee",
            "category": "goods_services",
            "activity_type": "coffee_purchase",
            "quantities": [
                {
                    "value": 1,
                    "unit": "item",
                    "dimension": "number",
                    "surface": "a takeaway coffee",
                    "evidence": "inferred_from_singular_phrase",
                }
            ],
            "entities": {"item": "coffee", "purchase_context": "takeaway"},
        }
    ])
    llm_extractor = LLMStructuredEventExtractor(FakeLLMClient(payload), FallbackExtractor([]))
    direct_events = llm_extractor.extract(
        JournalPreprocessor().preprocess("I grabbed a takeaway coffee.")
    )

    assert direct_events[0].quantities == []

    result = CarbonPipelineV2(
        event_extractor=llm_extractor,
        emission_estimator=fake_climatiq_estimator,
    ).run("I grabbed a takeaway coffee.").model_dump()

    detail = result["details"][0]
    assert detail["status"] == "estimated"
    assert detail["parameters"]["number"] == 1
    assert "coffee_purchase.inferred_single_serving" in _assumption_codes(detail)


def test_bag_bin_or_bottle_waste_mass_is_not_invented(fake_climatiq_estimator):
    payload = _json([
        {
            "raw_text": "took out a bag of rubbish",
            "category": "waste",
            "activity_type": "landfill_waste",
            "quantities": [
                {
                    "value": 1,
                    "unit": "kg",
                    "dimension": "weight",
                    "surface": "bag of rubbish",
                    "evidence": "inferred",
                }
            ],
            "entities": {"material_class": "general_waste", "disposal_method": "landfill"},
        }
    ])
    result = CarbonPipelineV2(
        event_extractor=LLMStructuredEventExtractor(FakeLLMClient(payload), FallbackExtractor([])),
        emission_estimator=fake_climatiq_estimator,
    ).run("I took out a bag of rubbish.").model_dump()

    detail = result["details"][0]
    assert detail["activity_type"] == "landfill_waste"
    assert detail["status"] == "unresolved"
    assert "weight" not in detail["parameters"]
    assert detail["issues"][0]["code"] in {
        "waste.disposal_method.ambiguous",
        "waste.missing_weight",
    }


def test_fake_llm_outputs_for_everyday_families_produce_safe_candidates():
    journal = JournalPreprocessor().preprocess(
        "I grabbed a takeaway coffee. I ordered a beef burrito. I recycled 500 g of bottles. "
        "I ran the heater for 3 hours. I was gaming on my PC for a few hours."
    )
    payload = _json([
        {
            "raw_text": "grabbed a takeaway coffee",
            "category": "goods_services",
            "activity_type": "coffee_purchase",
            "entities": {"item": "coffee"},
        },
        {
            "raw_text": "ordered a beef burrito",
            "category": "goods_services",
            "activity_type": "restaurant_meal",
            "entities": {"item": "beef burrito"},
        },
        {
            "raw_text": "recycled 500 g of bottles",
            "category": "waste",
            "activity_type": "recycling",
            "quantities": [
                {"value": 500, "unit": "g", "dimension": "weight", "surface": "500 g"}
            ],
            "entities": {"material": "bottles"},
        },
        {
            "raw_text": "ran the heater for 3 hours",
            "category": "energy",
            "activity_type": "space_heater_use",
            "entities": {"device": "heater"},
        },
        {
            "raw_text": "gaming on my PC for a few hours",
            "category": "energy",
            "activity_type": "generic_energy_use",
            "entities": {"device": "PC"},
        },
    ])

    events = LLMStructuredEventExtractor(FakeLLMClient(payload)).extract(journal)

    assert [event.activity_type for event in events] == [
        "coffee_purchase",
        "restaurant_meal",
        "recycling",
        "space_heater_use",
        "generic_energy_use",
    ]
    assert events[1].entities["product_class"] == "beef_burrito"
    assert events[4].entities["device"] == "personal_computer"


def test_estimate_v2_succeeds_when_llm_adapter_returns_invalid_output(
    monkeypatch,
    fake_climatiq_estimator,
):
    app_module.is_ready = True
    app_module.preload_error = None
    bad_llm_extractor = LLMStructuredEventExtractor(
        FakeLLMClient("not-json"),
        JournalEventExtractor(),
    )
    pipeline = CarbonPipelineV2(
        event_extractor=bad_llm_extractor,
        emission_estimator=fake_climatiq_estimator,
    )
    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: pipeline.run(journal).model_dump(by_alias=True),
    )

    response = client.post(
        "/api/estimate-v2",
        json={"journal": "I turned on the heater for 3 hours."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["details"][0]["activity_type"] == "space_heater_use"
    assert data["details"][0]["status"] == "estimated"


def test_v1_estimate_still_works_after_llm_adapter_changes(monkeypatch):
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


def _event(raw_text, category, activity_type):
    return CarbonEvent(
        raw_text=raw_text,
        category=category,
        activity_type=activity_type,
        confidence=Confidence.from_score(0.8),
    )


def _json(events):
    return json.dumps({"events": events})


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]
