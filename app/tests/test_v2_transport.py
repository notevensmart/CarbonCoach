from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.pipeline_v2.journal_preprocessor import JournalPreprocessor
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer


client = TestClient(app)


def test_preprocessor_normalizes_distance_units_and_vehicle_typos():
    result = JournalPreprocessor().preprocess("I rode 7km in a toytoa camery.")

    assert result.raw_journal == "I rode 7km in a toytoa camery."
    assert "7 km" in result.cleaned_journal
    assert "toyota camry" in result.cleaned_journal
    assert [correction.from_text for correction in result.corrections] == [
        "7km",
        "toytoa",
        "camery",
    ]


def test_quantity_normalizer_extracts_explicit_distance():
    quantities = QuantityNormalizer().normalize("I drove 10 km in a petrol car.")

    assert len(quantities) == 1
    assert quantities[0].dimension == "distance"
    assert quantities[0].value == 10
    assert quantities[0].unit == "km"
    assert quantities[0].confidence == 0.95


def test_quantity_normalizer_interprets_compact_k_only_with_distance_context():
    accepted = QuantityNormalizer().normalize("I took a 7k ride.")
    rejected = QuantityNormalizer().normalize("I spent 7k on furniture.")

    assert accepted[0].dimension == "distance"
    assert accepted[0].value == 7
    assert accepted[0].unit == "km"
    assert accepted[0].confidence == 0.72
    assert rejected == []


def test_pipeline_v2_estimates_explicit_petrol_car_distance(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 10 km in a petrol car.")

    assert detail["status"] == "estimated"
    assert detail["source"] == "climatiq"
    assert detail["category"] == "transport"
    assert detail["activity_type"] == "car_ride"
    assert detail["parameters"]["distance"] == 10
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["parameters"]["vehicle_size"] == "medium"
    assert detail["confidence"]["level"] == "high"
    assert detail["co2e"] == 1.92
    assert "vehicle.generic_car.default_medium" in _assumption_codes(detail)


def test_pipeline_v2_estimates_compact_k_ride_with_assumption(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took a 7k ride.")

    assert detail["parameters"]["distance"] == 7
    assert detail["confidence"] == {"score": 0.6, "level": "medium"}
    assert detail["co2e"] == 1.344
    assert "distance.compact_k_context_km" in _assumption_codes(detail)
    assert "vehicle.generic_car.default_petrol_medium" in _assumption_codes(detail)


def test_pipeline_v2_rejects_compact_k_purchase_context_as_distance():
    result = CarbonPipelineV2().run("I spent 7k on furniture.").model_dump()

    assert result["details"] == []
    assert result["total"]["co2e"] == 0


def test_pipeline_v2_uses_toyota_camry_default(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took a 7 km ride in a Toyota Camry.")

    assert detail["parameters"]["distance"] == 7
    assert detail["parameters"]["vehicle_make"] == "toyota"
    assert detail["parameters"]["vehicle_model"] == "camry"
    assert detail["parameters"]["vehicle_size"] == "medium"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["confidence"] == {"score": 0.65, "level": "medium"}
    assert _assumption_codes(detail) == ["vehicle.toyota_camry.default_petrol_medium"]


def test_pipeline_v2_records_typo_corrected_camry_with_lower_confidence(v2_pipeline):
    exact = _single_detail(v2_pipeline, "I took a 7 km ride in a Toyota Camry.")
    typo = _single_detail(v2_pipeline, "I took a 7 km ride in a toytoa camery.")

    assert typo["parameters"]["vehicle_make"] == "toyota"
    assert typo["parameters"]["vehicle_model"] == "camry"
    assert typo["confidence"]["score"] < exact["confidence"]["score"]
    assert "vehicle.toyota_camry.default_petrol_medium" in _assumption_codes(typo)
    assert "preprocessing.vehicle_typo.toytoa" in _issue_codes(typo)
    assert "preprocessing.vehicle_typo.camery" in _issue_codes(typo)


def test_pipeline_v2_explicit_electric_camry_overrides_petrol_default(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 7 km in my electric Toyota Camry.")

    assert detail["parameters"]["fuel_type"] == "electric"
    assert detail["parameters"]["vehicle_size"] == "medium"
    assert detail["confidence"]["level"] == "high"
    assert "vehicle.fuel_type.user_override" in _assumption_codes(detail)
    assert "vehicle.toyota_camry.default_petrol_medium" not in _assumption_codes(detail)


def test_pipeline_v2_uses_tesla_model_3_default(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove my Tesla Model 3 for 8 km.")

    assert detail["parameters"]["distance"] == 8
    assert detail["parameters"]["vehicle_make"] == "tesla"
    assert detail["parameters"]["vehicle_model"] == "model 3"
    assert detail["parameters"]["fuel_type"] == "electric"
    assert detail["confidence"] == {"score": 0.85, "level": "high"}
    assert _assumption_codes(detail) == ["vehicle.tesla_model_3.default_electric"]


def test_pipeline_v2_estimates_diesel_suv(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 12 km in a diesel SUV.")

    assert detail["parameters"]["distance"] == 12
    assert detail["parameters"]["fuel_type"] == "diesel"
    assert detail["parameters"]["vehicle_size"] == "large"
    assert detail["parameters"]["vehicle_class"] == "suv"
    assert detail["confidence"]["level"] == "high"
    assert detail["co2e"] == 3.24


def test_pipeline_v2_preserves_unknown_named_vehicle_with_visible_fallback(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took a 5 km ride in a BMW X5.")

    assert detail["parameters"]["vehicle_description"] == "BMW X5"
    assert detail["parameters"]["vehicle_size"] == "medium"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["co2e"] == 0.96
    assert _assumption_codes(detail) == ["vehicle.named.default_petrol_medium"]
    assert "vehicle.named_model.unmapped" in _issue_codes(detail)


def test_pipeline_v2_uses_explicit_body_class_for_unknown_named_vehicle(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took a 5 km ride in a BMW X5 SUV.")

    assert detail["parameters"]["vehicle_description"] == "BMW X5"
    assert detail["parameters"]["vehicle_class"] == "suv"
    assert detail["parameters"]["vehicle_size"] == "large"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["co2e"] == 1.25
    assert _assumption_codes(detail) == ["vehicle.named.default_petrol"]
    assert "vehicle.named_model.unmapped" in _issue_codes(detail)


def test_pipeline_v2_uses_explicit_fuel_and_body_class_without_model_guessing(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 5 km in an electric BMW iX SUV.")

    assert detail["parameters"]["vehicle_description"] == "BMW iX"
    assert detail["parameters"]["vehicle_class"] == "suv"
    assert detail["parameters"]["fuel_type"] == "electric"
    assert detail["co2e"] == 0.6
    assert detail["assumptions"] == []
    assert "vehicle.named_model.unmapped" in _issue_codes(detail)


def test_pipeline_v2_tesla_diesel_contradiction_lowers_confidence_and_adds_issue(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove my Tesla using diesel for 10 km.")

    assert detail["parameters"]["fuel_type"] == "electric"
    assert detail["confidence"] == {"score": 0.5, "level": "medium"}
    assert "vehicle.tesla.default_electric" in _assumption_codes(detail)
    assert "vehicle.fuel_type.contradiction" in _issue_codes(detail)


def test_pipeline_v2_returns_transport_and_energy_events_in_one_journal(v2_pipeline):
    result = v2_pipeline.run(
        "I drove 10 km in a petrol car and turned on the heater for 3 hours."
    ).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == [
        "car_ride",
        "space_heater_use",
    ]
    assert result["details"][0]["status"] == "estimated"
    assert result["details"][1]["status"] == "estimated"
    assert result["total"]["co2e"] == 4.62


def test_pipeline_v2_handles_transport_with_surrounding_text_and_compact_spacing(v2_pipeline):
    result = v2_pipeline.run(
        "After lunch I commuted 12km in a diesel SUV, then watched TV."
    ).model_dump()
    detail = result["details"][0]

    assert len(result["details"]) == 1
    assert detail["activity_type"] == "car_ride"
    assert detail["parameters"]["distance"] == 12
    assert detail["parameters"]["fuel_type"] == "diesel"
    assert detail["parameters"]["vehicle_size"] == "large"


def test_estimate_v2_api_returns_transport_response_shape(v2_api_pipeline):
    app_module.is_ready = True
    app_module.preload_error = None
    response = client.post(
        "/api/estimate-v2",
        json={"journal": "I took a 7 km ride in a Toyota Camry."},
    )

    assert response.status_code == 200
    data = response.json()
    detail = data["details"][0]

    assert data["version"] == "v2"
    assert data["total"]["source_breakdown"]["estimated"] == 1.344
    assert detail["category"] == "transport"
    assert detail["status"] == "estimated"
    assert detail["source"] == "climatiq"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["assumptions"][0]["code"] == "vehicle.toyota_camry.default_petrol_medium"


def _single_detail(v2_pipeline, journal: str) -> dict:
    result = v2_pipeline.run(journal).model_dump()
    assert len(result["details"]) == 1
    return result["details"][0]


def _assumption_codes(detail: dict) -> list[str]:
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail: dict) -> list[str]:
    return [issue["code"] for issue in detail["issues"]]
