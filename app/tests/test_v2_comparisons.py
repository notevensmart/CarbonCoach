import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import app as app_module
from app.app import app
from app.domain.impact_comparisons import (
    DEFAULT_COMPARISON_KEY,
    IMPACT_COMPARISON_DEFINITIONS,
    ImpactComparisonDefinition,
    build_impact_comparison,
)
from app.domain.models import Confidence, EstimateCoverage, EstimateTotal, FactorCandidate, SourceBreakdown
from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.pipeline import CarbonPipelineV2, _build_total


client = TestClient(app)


def _total(co2e: float, confidence_score: float) -> EstimateTotal:
    return EstimateTotal(
        co2e=co2e,
        confidence=Confidence.from_score(confidence_score),
        source_breakdown=SourceBreakdown(estimated=co2e),
    )


def test_maintained_petrol_car_comparison_metadata_is_validated():
    definition = IMPACT_COMPARISON_DEFINITIONS[DEFAULT_COMPARISON_KEY]

    assert definition.key == "average_petrol_car_distance"
    assert definition.display_label == "an average petrol car"
    assert definition.reference_label == "average petrol passenger car"
    assert definition.kg_co2e_per_unit == 0.192
    assert definition.unit == "km"
    assert definition.applicable_regions == ("AU",)
    assert definition.display_eligibility_rule == "positive_total_non_low_confidence"
    assert definition.eligible_confidence_levels == ("medium", "high")
    assert "operational travel emissions" in definition.applicability
    assert "National Greenhouse Accounts Factors 2025" in definition.source_note

    with pytest.raises(ValidationError):
        ImpactComparisonDefinition(
            key="bad",
            display_label="bad reference",
            reference_label="bad reference",
            kg_co2e_per_unit=0,
            unit="km",
            applicable_regions=("AU",),
            applicability="Australia",
            source_note="invalid coefficient",
            display_eligibility_rule="positive_total_non_low_confidence",
        )


def test_positive_eligible_total_converts_to_one_deterministic_comparison():
    first = build_impact_comparison(_total(3.072, 0.75))
    second = build_impact_comparison(_total(3.072, 0.75))

    assert first == second
    assert first is not None
    assert first.amount == 16
    assert first.unit == "km"
    assert first.input_total_kg_co2e == 3.072
    assert first.kg_co2e_per_unit == 0.192
    assert first.message == "Roughly equivalent to driving an average petrol car for 16 km."
    assert first.approximate is True


def test_zero_or_low_confidence_total_produces_no_comparison():
    assert build_impact_comparison(_total(0, 0.75)) is None
    assert build_impact_comparison(_total(2, 0.49)) is None


def test_partial_coverage_suppresses_otherwise_eligible_comparison():
    coverage = EstimateCoverage(
        represented_activity_count=2,
        included_in_total_count=1,
        unresolved_count=1,
        not_estimated_count=0,
        failed_count=0,
        estimate_is_partial=True,
    )

    assert build_impact_comparison(_total(2, 0.75), coverage=coverage) is None


def test_missing_invalid_or_incompatible_metadata_produces_no_comparison():
    total = _total(2, 0.75)
    invalid = {
        DEFAULT_COMPARISON_KEY: {
            "key": DEFAULT_COMPARISON_KEY,
            "display_label": "an average petrol car",
            "reference_label": "average petrol passenger car",
            "kg_co2e_per_unit": 0,
            "unit": "km",
            "applicable_regions": ("AU",),
            "applicability": "Australia",
            "source_note": "invalid coefficient",
            "display_eligibility_rule": "positive_total_non_low_confidence",
        }
    }

    assert build_impact_comparison(total, definitions={}) is None
    assert build_impact_comparison(total, definitions=invalid) is None
    assert build_impact_comparison(total, region="US") is None


def test_comparison_generation_does_not_change_estimate_calculations(v2_pipeline, monkeypatch):
    result = v2_pipeline.run("I drove 16 km in a petrol car.")
    total_from_details = _build_total(result.details)
    monkeypatch.setattr(
        "app.pipeline_v2.pipeline.build_impact_comparison",
        lambda total, **kwargs: None,
    )
    without_comparison = v2_pipeline.run("I drove 16 km in a petrol car.")

    assert result.comparison is not None
    assert without_comparison.comparison is None
    assert result.comparison.amount == 16
    assert result.total == total_from_details
    assert result.total == without_comparison.total
    assert result.details == without_comparison.details
    assert result.total.co2e == 3.072
    assert result.total.source_breakdown.estimated == 3.072
    assert result.details[0].co2e == 3.072
    assert result.total.confidence == result.details[0].confidence


def test_estimate_v2_api_includes_eligible_comparison(v2_api_pipeline):
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post("/api/estimate-v2", json={"journal": "I used 5 kWh of electricity."})
    repeated = client.post("/api/estimate-v2", json={"journal": "I used 5 kWh of electricity."})

    assert response.status_code == 200
    comparison = response.json()["comparison"]
    assert repeated.status_code == 200
    assert repeated.json()["comparison"] == comparison
    assert comparison["key"] == DEFAULT_COMPARISON_KEY
    assert comparison["amount"] == 16
    assert comparison["input_total_kg_co2e"] == 3.0
    assert comparison["kg_co2e_per_unit"] == 0.192


def test_estimate_v2_api_returns_no_comparison_for_zero_total(v2_api_pipeline):
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post("/api/estimate-v2", json={"journal": "I studied all afternoon."})

    assert response.status_code == 200
    assert response.json()["total"]["co2e"] == 0
    assert response.json()["comparison"] is None


class LowConfidenceSuccessfulEstimator:
    def estimate(self, event, parameters):
        return EmissionEstimateResult(
            ok=True,
            co2e=1.0,
            co2e_unit="kg",
            activity_id="fixture.low-confidence",
            factor=FactorCandidate(
                activity_id="fixture.low-confidence",
                name="Fixture low-confidence factor",
                unit_type="Energy",
                score=0.40,
            ),
        )


def test_estimate_v2_api_returns_no_comparison_for_positive_low_confidence_total(monkeypatch):
    low_confidence_pipeline = CarbonPipelineV2(
        emission_estimator=LowConfidenceSuccessfulEstimator()
    )
    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: low_confidence_pipeline.run(journal).model_dump(by_alias=True),
    )
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post("/api/estimate-v2", json={"journal": "I used 5 kWh of electricity."})

    assert response.status_code == 200
    assert response.json()["total"]["co2e"] == 1.0
    assert response.json()["total"]["confidence"]["level"] == "low"
    assert response.json()["comparison"] is None
