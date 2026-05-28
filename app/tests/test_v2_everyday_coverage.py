import pytest
from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.domain.models import CarbonEvent, Confidence, FactorCandidate
from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.parameter_builders import GoodsServicesParameterBuilder, WasteParameterBuilder
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer
from app.pipeline_v2.validator import FactorCompatibilityValidator


MANDATORY_JOURNAL = (
    "Today I drove around 12 km to work and grabbed a takeaway coffee on the way. "
    "During lunch I ordered a beef burrito and a soft drink through a delivery app. "
    "After getting home I ran the heater for most of the evening while gaming on my PC "
    "for a few hours. Later I took out a bag of rubbish that had some food packaging "
    "and plastic bottles in it."
)
client = TestClient(app)


def test_quantity_normalizer_adds_weight_money_natural_half_and_product_counts():
    quantities = QuantityNormalizer().normalize(
        "I bought two coffees for $6 and recycled half a kilogram of cardboard plus 500 g plastic."
    )
    by_surface = {quantity.surface: quantity for quantity in quantities}

    assert by_surface["two coffees"].dimension == "number"
    assert by_surface["two coffees"].value == 2
    assert by_surface["$6"].dimension == "money"
    assert by_surface["half a kilogram"].value == 0.5
    assert by_surface["500 g"].value == 0.5


@pytest.mark.parametrize(
    ("journal", "activity_types", "statuses"),
    [
        ("I grabbed a takeaway coffee.", ["coffee_purchase"], ["estimated"]),
        ("I bought two coffees on the way to work.", ["coffee_purchase"], ["estimated"]),
        ("I had 2 flat whites.", ["coffee_purchase"], ["estimated"]),
        ("I spent $6 on coffee.", ["coffee_purchase"], ["unresolved"]),
        ("I ordered a beef burrito for lunch.", ["restaurant_meal"], ["estimated"]),
        (
            "I ordered a beef burrito and a soft drink.",
            ["restaurant_meal", "food_purchase"],
            ["estimated", "estimated"],
        ),
        ("I ordered takeaway through a delivery app.", ["restaurant_meal"], ["unresolved"]),
        ("I bought groceries for dinner.", ["food_purchase"], ["unresolved"]),
        ("I bought 1 kg of beef.", ["food_purchase"], ["estimated"]),
        (
            "I bought an oat milk coffee and a shirt.",
            ["coffee_purchase", "clothing_purchase"],
            ["unresolved", "unresolved"],
        ),
        (
            "I bought coffee, then drove 8 km home.",
            ["coffee_purchase", "car_ride"],
            ["estimated", "estimated"],
        ),
    ],
)
def test_goods_services_coverage_matrix(v2_pipeline, journal, activity_types, statuses):
    details = v2_pipeline.run(journal).model_dump()["details"]

    assert [detail["activity_type"] for detail in details] == activity_types
    assert [detail["status"] for detail in details] == statuses


def test_goods_singular_assumption_is_visible_and_less_confident_than_explicit_count(v2_pipeline):
    assumed = v2_pipeline.run("I grabbed a takeaway coffee.").model_dump()["details"][0]
    explicit = v2_pipeline.run("I bought two coffees.").model_dump()["details"][0]

    assert assumed["parameters"]["number"] == 1
    assert assumed["parameter_confidence"]["score"] < explicit["parameter_confidence"]["score"]
    assert "coffee_purchase.inferred_single_serving" in _assumption_codes(assumed)
    assert explicit["parameters"]["number"] == 2
    assert "coffee_purchase.inferred_single_serving" not in _assumption_codes(explicit)


def test_money_does_not_become_coffee_count_and_delivery_is_not_silently_estimated(v2_pipeline):
    money = v2_pipeline.run("I spent $6 on coffee.").model_dump()["details"][0]
    delivery = v2_pipeline.run(
        "I ordered a beef burrito and a soft drink through a delivery app."
    ).model_dump()["details"]

    assert money["status"] == "unresolved"
    assert money["parameters"] == {"product_class": "coffee", "money": 6.0, "money_unit": "USD"}
    assert money["issues"][0]["code"] == "goods_services.money_factor_unavailable"
    assert all(detail["parameters"]["delivery_context"] == "delivery_app" for detail in delivery)
    assert all(
        "goods_services.delivery_transport.not_included" in _issue_codes(detail)
        for detail in delivery
    )


@pytest.mark.parametrize(
    ("journal", "activity_type", "status", "weight"),
    [
        ("I recycled 500 g of plastic bottles.", "recycling", "estimated", 0.5),
        ("I recycled half a kilogram of cardboard.", "recycling", "estimated", 0.5),
        ("I composted 2 kg of food scraps.", "composting", "estimated", 2),
        ("I put 1 kg of general rubbish in the landfill bin.", "landfill_waste", "estimated", 1),
        ("I threw away 750 g of mixed packaging.", "landfill_waste", "estimated", 0.75),
        ("I put glass and plastic in the recycling bin.", "recycling", "unresolved", None),
        (
            "I took out a bag of rubbish containing packaging and plastic bottles.",
            "landfill_waste",
            "unresolved",
            None,
        ),
    ],
)
def test_waste_coverage_matrix(v2_pipeline, journal, activity_type, status, weight):
    detail = v2_pipeline.run(journal).model_dump()["details"][0]

    assert detail["activity_type"] == activity_type
    assert detail["status"] == status
    if weight is not None:
        assert detail["parameters"]["weight"] == weight
        assert detail["parameters"]["weight_unit"] == "kg"
    else:
        assert "weight" not in detail["parameters"]


@pytest.mark.parametrize(
    "journal",
    [
        "I sat at the coffee table for an hour.",
        "I reviewed a meal plan.",
        "I worked on Java while drinking water.",
        "I had plastic bottles in my backpack.",
        "That meeting was a waste of time.",
    ],
)
def test_nearby_negative_phrases_do_not_create_everyday_events(v2_pipeline, journal):
    assert v2_pipeline.run(journal).details == []


def test_mixed_events_preserve_order_parameters_totals_and_coverage(v2_pipeline):
    result = v2_pipeline.run(
        "I bought two coffees, then drove 8 km home, and recycled 500 g of plastic bottles."
    ).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == [
        "coffee_purchase",
        "car_ride",
        "recycling",
    ]
    assert result["details"][0]["parameters"]["number"] == 2
    assert "distance" not in result["details"][0]["parameters"]
    assert result["details"][1]["parameters"]["distance"] == 8
    assert "weight" not in result["details"][1]["parameters"]
    assert result["details"][2]["parameters"]["weight"] == 0.5
    assert result["total"]["co2e"] == round(sum(detail["co2e"] for detail in result["details"]), 3)
    assert result["coverage"] == {
        "represented_activity_count": 3,
        "included_in_total_count": 3,
        "unresolved_count": 0,
        "not_estimated_count": 0,
        "failed_count": 0,
        "estimate_is_partial": False,
    }


def test_mandatory_everyday_journal_is_visible_partial_and_has_no_comparison(v2_pipeline):
    result = v2_pipeline.run(MANDATORY_JOURNAL).model_dump()
    details = result["details"]

    assert [detail["activity_type"] for detail in details] == [
        "car_ride",
        "coffee_purchase",
        "restaurant_meal",
        "food_purchase",
        "space_heater_use",
        "generic_energy_use",
        "landfill_waste",
        "landfill_waste",
    ]
    assert [detail["status"] for detail in details] == [
        "estimated",
        "estimated",
        "estimated",
        "estimated",
        "unresolved",
        "unresolved",
        "unresolved",
        "unresolved",
    ]
    assert details[3]["parameters"]["delivery_context"] == "delivery_app"
    assert details[5]["parameters"]["device"] == "personal_computer"
    assert details[6]["parameters"]["disposal_method"] == "unknown"
    assert result["coverage"] == {
        "represented_activity_count": 8,
        "included_in_total_count": 4,
        "unresolved_count": 4,
        "not_estimated_count": 0,
        "failed_count": 0,
        "estimate_is_partial": True,
    }
    assert result["comparison"] is None


def test_not_estimated_event_does_not_make_eligible_result_partial(v2_pipeline):
    result = v2_pipeline.run("I used 5 kWh of electricity and walked 2 km.").model_dump()

    assert result["coverage"]["not_estimated_count"] == 1
    assert result["coverage"]["estimate_is_partial"] is False
    assert result["comparison"] is not None


def test_failure_in_goods_event_isolated_from_transport_and_makes_coverage_partial():
    class RaisingCoffeeEstimator:
        def estimate(self, event, parameters):
            if event.activity_type == "coffee_purchase":
                raise RuntimeError("fixture provider exception")
            return EmissionEstimateResult(ok=True, co2e=1.0, co2e_unit="kg")

    result = CarbonPipelineV2(emission_estimator=RaisingCoffeeEstimator()).run(
        "I bought two coffees and drove 8 km home."
    ).model_dump()

    assert [detail["status"] for detail in result["details"]] == ["failed", "estimated"]
    assert result["total"]["co2e"] == 1.0
    assert result["coverage"]["failed_count"] == 1
    assert result["coverage"]["estimate_is_partial"] is True
    assert result["comparison"] is None


def test_goods_and_waste_unit_compatibility_rejects_cross_category_records():
    goods_event = _event("goods_services", "coffee_purchase", {"product_class": "coffee"})
    goods_event = goods_event.model_copy(
        update={"quantities": QuantityNormalizer().normalize("two coffees", goods_event)}
    )
    waste_event = _event("waste", "recycling", {"disposal_method": "recycling", "material_class": "plastic"})
    waste_event = waste_event.model_copy(
        update={"quantities": QuantityNormalizer().normalize("500 g plastic", waste_event)}
    )
    goods_parameters = GoodsServicesParameterBuilder().build(goods_event).parameters
    waste_parameters = WasteParameterBuilder().build(waste_event).parameters
    validator = FactorCompatibilityValidator()

    assert validator.validate_record(
        goods_event,
        goods_parameters,
        {"unit_type": "Number", "sector": "Goods", "category": "Food"},
    ).compatible
    assert validator.validate_record(
        waste_event,
        waste_parameters,
        {"unit_type": "Weight", "sector": "Waste", "category": "Waste"},
    ).compatible
    assert not validator.validate_record(
        goods_event,
        goods_parameters,
        {"unit_type": "Weight", "sector": "Waste", "category": "Waste"},
    ).compatible


def test_factor_confidence_for_goods_does_not_rescale_co2e():
    class GoodsFactorEstimator:
        def __init__(self, score):
            self.score = score

        def estimate(self, event, parameters):
            return EmissionEstimateResult(
                ok=True,
                co2e=0.5,
                co2e_unit="kg",
                factor=FactorCandidate(
                    activity_id="fixture.coffee",
                    name="Coffee serving",
                    sector="Goods",
                    category="Food",
                    unit_type="Number",
                    score=self.score,
                ),
            )

    high = CarbonPipelineV2(emission_estimator=GoodsFactorEstimator(0.95)).run(
        "I bought two coffees."
    ).details[0]
    medium = CarbonPipelineV2(emission_estimator=GoodsFactorEstimator(0.6)).run(
        "I bought two coffees."
    ).details[0]

    assert high.co2e == medium.co2e == 0.5
    assert high.confidence.score == 0.93
    assert medium.confidence.score == 0.6


def test_api_serializes_mandatory_partial_coverage_and_suppressed_comparison(v2_api_pipeline):
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post("/api/estimate-v2", json={"journal": MANDATORY_JOURNAL})

    assert response.status_code == 200
    result = response.json()
    assert result["coverage"]["estimate_is_partial"] is True
    assert result["coverage"]["represented_activity_count"] == len(result["details"])
    assert result["comparison"] is None


def _event(category, activity_type, entities):
    return CarbonEvent(
        raw_text=activity_type,
        category=category,
        activity_type=activity_type,
        entities=entities,
        confidence=Confidence.from_score(0.8),
    )


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail):
    return [issue["code"] for issue in detail["issues"]]
