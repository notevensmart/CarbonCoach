from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.parameter_builders import EnergyParameterBuilder
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer
from app.domain.models import CarbonEvent, Confidence


def test_journal_preprocessing_preserves_raw_text_and_records_unit_corrections():
    raw = "I used a 2kw heater for 3hrs and used 5kwh later."

    result = JournalPreprocessor().preprocess(raw)

    assert result.raw_journal == raw
    assert "2 kW" in result.cleaned_journal
    assert "3 hours" in result.cleaned_journal
    assert "5 kWh" in result.cleaned_journal
    assert [correction.from_text for correction in result.corrections] == [
        "2kw",
        "3hrs",
        "5kwh",
    ]


def test_quantity_normalization_for_power_duration_and_energy():
    quantities = QuantityNormalizer().normalize("I used a 2 kW heater for 3 hours and 5 kWh.")

    by_dimension = {quantity.dimension: quantity for quantity in quantities}

    assert by_dimension["power"].value == 2
    assert by_dimension["power"].unit == "kW"
    assert by_dimension["duration"].value == 3
    assert by_dimension["duration"].unit == "hours"
    assert by_dimension["energy"].value == 5
    assert by_dimension["energy"].unit == "kWh"


def test_energy_builder_derives_kwh_from_explicit_power_and_duration():
    event = _energy_event("space_heater_use", "I used a 2 kW heater for 3 hours.")
    event = event.model_copy(
        update={
            "quantities": QuantityNormalizer().normalize("I used a 2 kW heater for 3 hours.")
        }
    )

    result = EnergyParameterBuilder().build(event)

    assert result.parameters["energy"] == 6
    assert result.parameters["energy_unit"] == "kWh"
    assert result.parameters["power"] == 2
    assert result.parameters["duration"] == 3
    assert result.confidence.level == "high"
    assert result.confidence.score == 0.90


def test_energy_builder_uses_default_heater_power_with_assumptions():
    event = _energy_event("space_heater_use", "I turned on the heater for 3 hours.")
    event = event.model_copy(
        update={"quantities": QuantityNormalizer().normalize("heater for 3 hours")}
    )

    result = EnergyParameterBuilder().build(event)

    assert result.parameters["energy"] == 4.5
    assert result.parameters["power"] == 1.5
    assert result.confidence.level == "medium"
    assert result.confidence.score == 0.60
    assert _assumption_codes(result.assumptions) == [
        "space_heater.default_power",
        "region.default_au_electricity",
    ]


def test_energy_builder_uses_direct_kwh_for_electricity():
    event = _energy_event("electricity_use", "I used 5 kWh of electricity.")
    event = event.model_copy(
        update={"quantities": QuantityNormalizer().normalize("I used 5 kWh of electricity.")}
    )

    result = EnergyParameterBuilder().build(event)

    assert result.parameters == {"energy": 5, "energy_unit": "kWh"}
    assert result.confidence.level == "high"
    assert result.confidence.score == 0.95
    assert _assumption_codes(result.assumptions) == ["region.default_au_electricity"]


def test_pipeline_v2_explicit_heater_response():
    result = CarbonPipelineV2().run("I used a 2 kW heater for 3 hours.").model_dump()
    detail = result["details"][0]

    assert result["version"] == "v2"
    assert result["total"]["co2e"] == 3.6
    assert result["total"]["source_breakdown"]["fallback_estimated"] == 3.6
    assert detail["category"] == "energy"
    assert detail["activity_type"] == "space_heater_use"
    assert detail["status"] == "fallback_estimated"
    assert detail["parameters"]["energy"] == 6
    assert detail["confidence"]["level"] == "high"


def test_pipeline_v2_duration_only_heater_response():
    result = CarbonPipelineV2().run("I turned on the heater for 3 hours.").model_dump()
    detail = result["details"][0]

    assert result["total"]["co2e"] == 2.7
    assert detail["parameters"]["energy"] == 4.5
    assert detail["confidence"] == {"score": 0.6, "level": "medium"}
    assert _assumption_codes(detail["assumptions"]) == [
        "space_heater.default_power",
        "region.default_au_electricity",
    ]
    assert detail["issues"] == []


def test_pipeline_v2_direct_electricity_response():
    result = CarbonPipelineV2().run("I used 5 kWh of electricity.").model_dump()
    detail = result["details"][0]

    assert result["total"]["co2e"] == 3.0
    assert detail["activity_type"] == "electricity_use"
    assert detail["parameters"] == {"energy": 5, "energy_unit": "kWh"}
    assert detail["confidence"] == {"score": 0.95, "level": "high"}
    assert _assumption_codes(detail["assumptions"]) == ["region.default_au_electricity"]


def _energy_event(activity_type, raw_text):
    return CarbonEvent(
        raw_text=raw_text,
        category="energy",
        activity_type=activity_type,
        confidence=Confidence.from_score(0.80),
    )


def _assumption_codes(assumptions):
    return [assumption["code"] if isinstance(assumption, dict) else assumption.code for assumption in assumptions]

