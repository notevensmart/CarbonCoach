import pytest
from pydantic import ValidationError

from app.domain.models import CarbonEvent, Confidence, Quantity


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0.80, "high"),
        (1.00, "high"),
        (0.79, "medium"),
        (0.50, "medium"),
        (0.49, "low"),
        (0.00, "low"),
    ],
)
def test_confidence_score_to_level_mapping(score, level):
    assert Confidence.from_score(score).level == level


def test_confidence_rejects_mismatched_level():
    with pytest.raises(ValidationError):
        Confidence(score=0.90, level="medium")


def test_domain_models_validate_controlled_fields():
    quantity = Quantity(
        value=5,
        unit="kWh",
        dimension="energy",
        surface="5 kWh",
    )
    event = CarbonEvent(
        raw_text="I used 5 kWh of electricity.",
        category="energy",
        activity_type="electricity_use",
        quantities=[quantity],
        confidence=Confidence.from_score(0.95),
    )

    assert event.quantities[0].dimension == "energy"

    with pytest.raises(ValidationError):
        CarbonEvent(
            raw_text="I ate lunch.",
            category="food",
            activity_type="restaurant_meal",
        )

