from app.services.param_utils import (
    FallbackEstimator,
    JournalParameterExtractor,
    parse_quantity_candidates,
)


def test_extracts_distance_from_journal_for_transport():
    extractor = JournalParameterExtractor()

    result = extractor.extract(
        unit_type="Distance",
        journal_entry="I took a 5 km bus ride to work.",
        label="bus ride",
        category="transport",
    )

    assert result.parameters == {"distance": 5.0, "distance_unit": "km"}
    assert result.source == "journal"
    assert result.confidence == "high"


def test_converts_miles_to_kilometers():
    candidates = parse_quantity_candidates("I drove 10 miles to the store.")

    distance = next(candidate for candidate in candidates if candidate.dimension == "distance")
    assert distance.value == 16.0934
    assert distance.unit == "km"


def test_extracts_weight_for_waste():
    extractor = JournalParameterExtractor()

    result = extractor.extract(
        unit_type="Weight",
        journal_entry="I recycled 500 g of plastic packaging.",
        label="recycling",
        category="waste",
    )

    assert result.parameters == {"weight": 0.5, "weight_unit": "kg"}
    assert result.source == "journal"


def test_uses_default_when_quantity_is_missing():
    extractor = JournalParameterExtractor()

    result = extractor.extract(
        unit_type="Energy",
        journal_entry="I used electricity at home today.",
        label="electricity use",
        category="energy",
    )

    assert result.parameters == {"energy": 5, "energy_unit": "kWh"}
    assert result.source == "default"
    assert result.confidence == "low"


def test_fallback_estimator_uses_parameters():
    estimator = FallbackEstimator()

    result = estimator.estimate(
        category="transport",
        unit_type="Distance",
        parameters={"distance": 12, "distance_unit": "km"},
    )

    assert result["co2e"] == 2.16
    assert result["source"] == "fallback"
