import json
from pathlib import Path

import pytest

from app.domain.models import FactorCandidate
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator, EmissionEstimateResult
from app.pipeline_v2.pipeline import CarbonPipelineV2


GOLDEN_CASES = [
    json.loads(line)
    for line in (Path(__file__).parent / "fixtures" / "v2_golden_inputs.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
MULTI_SENTENCE_CASES = [
    json.loads(line)
    for line in (Path(__file__).parent / "fixtures" / "v2_multisentence_journals.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]


class FactorBackedEstimator:
    def __init__(self, scores=None):
        self.scores = scores or {}

    def estimate(self, event, parameters):
        score = self.scores.get(event.activity_type, self.scores.get("default", 0.90))
        unit_type = "Energy" if event.category == "energy" else "Distance"
        amount = float(parameters.get("energy", parameters.get("distance", 0)))
        return EmissionEstimateResult(
            ok=True,
            co2e=round(amount * 0.4, 3),
            co2e_unit="kg",
            activity_id=f"fixture.{event.activity_type}",
            factor=FactorCandidate(
                activity_id=f"fixture.{event.activity_type}",
                name=f"Fixture factor for {event.activity_type}",
                sector="Energy" if event.category == "energy" else "Transport",
                category="Electricity" if event.category == "energy" else "Vehicles",
                unit_type=unit_type,
                score=score,
                match_reasons=["structured fixture factor matched normalized dimensions"],
            ),
        )


def _offline_fallback_pipeline():
    return CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            activity_search=lambda query, limit: [],
        )
    )


@pytest.mark.parametrize("case", GOLDEN_CASES)
def test_v2_golden_regressions_use_deterministic_offline_path(case):
    detail = _offline_fallback_pipeline().run(case["input"]).model_dump()["details"][0]

    if "expected_status" in case:
        assert detail["status"] == case["expected_status"]
    if "expected_category" in case:
        assert detail["category"] == case["expected_category"]
    if "expected_activity_type" in case:
        assert detail["activity_type"] == case["expected_activity_type"]
    if "expected_energy_kwh" in case:
        assert detail["parameters"]["energy"] == case["expected_energy_kwh"]
    if "expected_distance_km" in case:
        assert detail["parameters"]["distance"] == case["expected_distance_km"]
    if "expected_fuel_type" in case:
        assert detail["parameters"]["fuel_type"] == case["expected_fuel_type"]
    if "expected_assumption_code" in case:
        assert case["expected_assumption_code"] in _assumption_codes(detail)
    if "expected_issue_code" in case:
        assert case["expected_issue_code"] in _issue_codes(detail)


@pytest.mark.parametrize("case", MULTI_SENTENCE_CASES)
def test_generated_multi_sentence_journals_keep_all_visible_events(case):
    result = _offline_fallback_pipeline().run(case["input"]).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == case[
        "expected_activity_types"
    ]
    assert [detail["status"] for detail in result["details"]] == case["expected_statuses"]
    assert result["total"]["co2e"] == case["expected_total_co2e"]


@pytest.mark.parametrize(
    "journal",
    [
        "I read a book for 2 hours.",
        "I was reading a novel this evening.",
        "I studied all afternoon.",
        "I studied for an exam after lunch.",
    ],
)
def test_personal_activity_matrix_returns_not_estimated(journal):
    detail = CarbonPipelineV2().run(journal).model_dump()["details"][0]

    assert detail["activity_type"] == "personal_activity"
    assert detail["status"] == "not_estimated"
    assert detail["co2e"] == 0
    assert "No direct operational emissions" in detail["parameters"]["emissions_boundary"]


@pytest.mark.parametrize(
    "journal",
    [
        "I used my thing for a while.",
        "I ran an appliance for a while.",
        "I used my device for 2 hours.",
    ],
)
def test_ambiguous_energy_matrix_returns_visible_unresolved_issue(journal):
    detail = CarbonPipelineV2().run(journal).model_dump()["details"][0]

    assert detail["activity_type"] == "generic_energy_use"
    assert detail["status"] == "unresolved"
    assert detail["source"] == "unresolved"
    assert _issue_codes(detail) == ["energy.activity.unspecified"]


@pytest.mark.parametrize(
    ("journal", "activity_type", "issue_code"),
    [
        (
            "I cooked dinner in the electric oven for 45 minutes.",
            "cooking_appliance_use",
            "energy.cooking_appliance_use.unsupported_factor",
        ),
        (
            "I had a 10 minute hot shower this morning.",
            "hot_water_use",
            "energy.hot_water_use.unsupported_factor",
        ),
        (
            "I used natural gas for cooking for 30 minutes.",
            "natural_gas_use",
            "energy.natural_gas_use.unsupported_factor",
        ),
        ("I watched TV for 2 hours.", "generic_energy_use", "energy.activity.unspecified"),
    ],
)
def test_explicit_unsupported_energy_neighbors_are_visible(journal, activity_type, issue_code):
    detail = CarbonPipelineV2().run(journal).model_dump()["details"][0]

    assert detail["activity_type"] == activity_type
    assert detail["status"] == "unresolved"
    assert _issue_codes(detail) == [issue_code]


def test_comma_separated_energy_activities_do_not_share_durations():
    result = _offline_fallback_pipeline().run(
        "While I charged my phone for 2 hours, I turned on the heater for 1 hour."
    ).model_dump()

    assert result["details"][0]["parameters"]["duration"] == 2
    assert result["details"][1]["parameters"]["duration"] == 1
    assert result["details"][1]["parameters"]["energy"] == 1.5


def test_raw_detail_text_preserves_original_formatting_and_typo_surfaces():
    result = _offline_fallback_pipeline().run(
        "I took a 7k ride in a toytoa camery. Later, I used 2kwh electricity."
    ).model_dump()

    assert result["details"][0]["raw_text"] == "I took a 7k ride in a toytoa camery"
    assert result["details"][1]["raw_text"] == "I used 2kwh electricity."
    assert result["details"][0]["parameters"]["vehicle_model"] == "camry"


def test_walk_in_shoes_is_not_misclassified_as_named_vehicle_transport():
    details = _offline_fallback_pipeline().run(
        "I went for a 3 km walk in my new shoes. I bought a shirt afterward."
    ).model_dump()["details"]

    assert [detail["activity_type"] for detail in details] == [
        "walking",
        "clothing_purchase",
    ]
    assert all(detail["activity_type"] != "car_ride" for detail in details)


def test_not_estimated_details_are_excluded_from_total_in_mixed_journal(v2_pipeline):
    result = v2_pipeline.run(
        "I used 5 kWh of electricity and read a book for 2 hours."
    ).model_dump()

    assert [detail["status"] for detail in result["details"]] == [
        "estimated",
        "not_estimated",
    ]
    assert result["total"]["co2e"] == 3.0
    assert result["total"]["source_breakdown"]["not_estimated"] == 0.0


def test_unresolved_and_not_estimated_events_do_not_hide_supported_event(v2_pipeline):
    result = v2_pipeline.run(
        "I studied all afternoon, then used my device for a while, "
        "then took a 5 km bus ride."
    ).model_dump()

    assert [detail["status"] for detail in result["details"]] == [
        "not_estimated",
        "unresolved",
        "estimated",
    ]
    assert result["total"]["co2e"] == 0.5


def test_empty_and_irrelevant_entries_are_safe_and_have_zero_total():
    pipeline = CarbonPipelineV2()

    for journal in ("", "I watched the sunset and wrote in my diary."):
        result = pipeline.run(journal).model_dump()
        assert result["details"] == []
        assert result["total"]["co2e"] == 0


def test_selected_medium_factor_caps_high_parameter_confidence():
    pipeline = CarbonPipelineV2(
        emission_estimator=FactorBackedEstimator({"electricity_use": 0.75})
    )

    detail = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert detail["parameter_confidence"] == {"score": 0.95, "level": "high"}
    assert detail["factor_confidence"] == {"score": 0.75, "level": "medium"}
    assert detail["source_confidence"] == {"score": 1.0, "level": "high"}
    assert detail["confidence"] == {"score": 0.75, "level": "medium"}


def test_high_factor_does_not_raise_assumed_parameter_confidence():
    pipeline = CarbonPipelineV2(
        emission_estimator=FactorBackedEstimator({"space_heater_use": 0.94})
    )

    detail = pipeline.run("I turned on the heater for 3 hours.").model_dump()["details"][0]

    assert detail["parameter_confidence"] == {"score": 0.6, "level": "medium"}
    assert detail["factor_confidence"] == {"score": 0.94, "level": "high"}
    assert detail["confidence"] == {"score": 0.6, "level": "medium"}


def test_fallback_factor_and_source_confidence_cap_overall_confidence():
    detail = _offline_fallback_pipeline().run(
        "I used 5 kWh of electricity."
    ).model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["parameter_confidence"] == {"score": 0.95, "level": "high"}
    assert detail["factor_confidence"] == {"score": 0.55, "level": "medium"}
    assert detail["source_confidence"] == {"score": 0.55, "level": "medium"}
    assert detail["confidence"] == {"score": 0.55, "level": "medium"}


def test_total_confidence_uses_factor_capped_event_confidences():
    pipeline = CarbonPipelineV2(
        emission_estimator=FactorBackedEstimator(
            {"electricity_use": 0.62, "space_heater_use": 0.92}
        )
    )

    result = pipeline.run(
        "I used 5 kWh of electricity and turned on the heater for 1 hour."
    ).model_dump()

    assert [detail["confidence"]["score"] for detail in result["details"]] == [0.62, 0.6]
    assert result["total"]["confidence"] == {"score": 0.61, "level": "medium"}


def test_factor_confidence_changes_displayed_confidence_not_emissions_amount():
    high = CarbonPipelineV2(
        emission_estimator=FactorBackedEstimator({"electricity_use": 0.95})
    ).run("I used 5 kWh of electricity.").model_dump()["details"][0]
    medium = CarbonPipelineV2(
        emission_estimator=FactorBackedEstimator({"electricity_use": 0.60})
    ).run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert high["co2e"] == medium["co2e"] == 2.0
    assert high["confidence"]["score"] == 0.95
    assert medium["confidence"]["score"] == 0.60


@pytest.mark.parametrize(
    "journal",
    [
        "I took a 5km bus ride.",
        "I caught the train for 12 km.",
        "I drove 10 km in a petrol car.",
        "I turned on the heater for 3 hours.",
    ],
)
def test_common_v1_visible_pathways_remain_nonzero_in_v2(v2_pipeline, journal):
    result = v2_pipeline.run(journal).model_dump()

    assert result["details"][0]["status"] == "estimated"
    assert result["total"]["co2e"] > 0


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail):
    return [issue["code"] for issue in detail["issues"]]
