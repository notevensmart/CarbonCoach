import json

from app.domain.models import CarbonEvent, CoachingRecommendation, Confidence
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.pipeline_v2.sustainability_coach import (
    LangChainCoachingClient,
    SustainabilityCoach,
    build_sustainability_coach,
)


class FakeCoachingClient:
    def __init__(self, payload="", exc=None):
        self.payload = payload
        self.exc = exc
        self.prompts = []

    def generate_coaching_json(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        return self.payload


class GreenAwareCoachingClient:
    def __init__(self):
        self.prompts = []

    def generate_coaching_json(self, prompt: str) -> str:
        self.prompts.append(prompt)
        feedback = []
        if '"activity_type":"walking"' in prompt:
            feedback.append("Walking was a lower-carbon choice in this entry.")
        return _coaching_json(positive_feedback=feedback)


class StaticEventExtractor:
    def __init__(self, events):
        self.events = events

    def extract(self, journal):
        return self.events


class MutatingCoach:
    def recommend(self, journal_entry, estimate):
        estimate.total.co2e = 999
        estimate.details.clear()
        if estimate.coverage is not None:
            estimate.coverage.included_in_total_count = 999
        return CoachingRecommendation(
            headline="Try one targeted transport swap",
            message="The completed estimate points to transport as the best place to start.",
            actions=[
                {
                    "title": "Compare a transit option",
                    "reason": "The car trip was the largest included activity.",
                    "activity_ref": "drove 10 km in a petrol car",
                }
            ],
        )


def test_valid_coaching_json_appears_in_pipeline_response(fake_climatiq_estimator):
    client = FakeCoachingClient(_coaching_json())
    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(client, enabled=True),
    )

    result = pipeline.run("I drove 10 km in a petrol car.")

    assert result.coaching is not None
    assert result.coaching.headline == "Your biggest opportunity is transport"
    assert result.coaching.actions[0].activity_ref == "drove 10 km in a petrol car"
    assert result.model_dump()["coaching"]["headline"] == "Your biggest opportunity is transport"
    assert len(client.prompts) == 1
    assert "Post-estimate context JSON" in client.prompts[0]
    assert "factor_diagnostics" not in client.prompts[0]


def test_invalid_coaching_json_is_omitted(fake_climatiq_estimator):
    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(
            FakeCoachingClient("not-json"),
            enabled=True,
        ),
    )

    result = pipeline.run("I drove 10 km in a petrol car.")

    assert result.coaching is None
    assert "coaching" not in result.model_dump()
    assert result.details[0].status == "estimated"


def test_invalid_coaching_schema_is_omitted(fake_climatiq_estimator):
    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(
            FakeCoachingClient(json.dumps({"headline": "Missing required message"})),
            enabled=True,
        ),
    )

    result = pipeline.run("I drove 10 km in a petrol car.")

    assert result.coaching is None
    assert result.total.co2e == 1.92


def test_coaching_exceptions_are_omitted(fake_climatiq_estimator):
    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(
            FakeCoachingClient(exc=TimeoutError("timed out")),
            enabled=True,
        ),
    )

    result = pipeline.run("I drove 10 km in a petrol car.")

    assert result.coaching is None
    assert result.details[0].status == "estimated"


def test_disabled_coaching_does_not_call_client(fake_climatiq_estimator):
    client = FakeCoachingClient(_coaching_json())
    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(client, enabled=False),
    )

    result = pipeline.run("I drove 10 km in a petrol car.")

    assert result.coaching is None
    assert client.prompts == []


def test_default_coaching_builder_uses_provider_key_without_flag(monkeypatch):
    monkeypatch.delenv("CARBONCOACH_V2_COACHING_ENABLED", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    coach = build_sustainability_coach()

    assert coach is not None
    assert isinstance(coach.client, LangChainCoachingClient)
    assert coach.client.api_key == "test-key"


def test_default_coaching_builder_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("CARBONCOACH_V2_COACHING_ENABLED", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    assert build_sustainability_coach() is None


def test_coaching_cannot_change_total_details_confidence_or_coverage(fake_climatiq_estimator):
    journal = "I drove 10 km in a petrol car."
    baseline = CarbonPipelineV2(emission_estimator=fake_climatiq_estimator).run(journal)
    coached = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=MutatingCoach(),
    ).run(journal)

    assert coached.coaching is not None
    assert coached.total == baseline.total
    assert coached.details == baseline.details
    assert coached.total.confidence == baseline.total.confidence
    assert coached.coverage == baseline.coverage
    assert coached.comparison == baseline.comparison


def test_partial_low_confidence_context_requires_directional_note(fake_climatiq_estimator):
    client = FakeCoachingClient(
        _coaching_json(
            confidence_note="This advice is directional because the estimate is partial.",
        )
    )
    pipeline = CarbonPipelineV2(
        event_extractor=StaticEventExtractor(
            [
                CarbonEvent(
                    raw_text="I took a trip across town.",
                    category="transport",
                    activity_type="car_ride",
                    confidence=Confidence.from_score(0.3),
                )
            ]
        ),
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(client, enabled=True),
    )

    result = pipeline.run("I took a trip across town.")

    assert result.coaching.confidence_note == (
        "This advice is directional because the estimate is partial."
    )
    assert '"directional_advice_required":true' in client.prompts[0]
    assert "include a confidence_note saying the advice is directional" in client.prompts[0]


def test_green_activities_can_produce_positive_feedback(fake_climatiq_estimator):
    client = GreenAwareCoachingClient()
    pipeline = CarbonPipelineV2(
        event_extractor=StaticEventExtractor(
            [
                CarbonEvent(
                    raw_text="I walked 2 km.",
                    category="transport",
                    activity_type="walking",
                    confidence=Confidence.from_score(0.9),
                ),
                CarbonEvent(
                    raw_text="I drove 5 km in a petrol car.",
                    category="transport",
                    activity_type="car_ride",
                    confidence=Confidence.from_score(0.86),
                ),
            ]
        ),
        emission_estimator=fake_climatiq_estimator,
        sustainability_coach=SustainabilityCoach(client, enabled=True),
    )

    result = pipeline.run("I walked 2 km. I drove 5 km in a petrol car.")

    assert result.coaching.positive_feedback == [
        "Walking was a lower-carbon choice in this entry."
    ]
    assert '"lower_carbon_choices"' in client.prompts[0]
    assert '"activity_type":"walking"' in client.prompts[0]


def _coaching_json(
    positive_feedback=None,
    confidence_note="This advice is based on the activities CarbonCoach could estimate.",
):
    return json.dumps(
        {
            "headline": "Your biggest opportunity is transport",
            "message": (
                "The car trip was the largest contributor today. If this trip is "
                "regular, compare transit, carpooling, or combining errands."
            ),
            "positive_feedback": positive_feedback or [],
            "actions": [
                {
                    "title": "Compare alternatives for the car trip",
                    "reason": "It was the largest estimated activity in this entry.",
                    "activity_ref": "drove 10 km in a petrol car",
                }
            ],
            "confidence_note": confidence_note,
        }
    )
