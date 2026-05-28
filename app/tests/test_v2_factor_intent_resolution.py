from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.domain.models import CarbonEvent, Confidence
from app.pipeline_v2.calculation_intent_resolver import CalculationIntentResolver
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever
from app.pipeline_v2.parameter_builders import WasteParameterBuilder
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer
from app.pipeline_v2.validator import FactorCompatibilityValidator
from app.services.climatiq_api import ClimatiqEstimate


client = TestClient(app)


def test_resolver_builds_independent_waste_material_and_method_intent():
    landfill = _event(
        "waste",
        "landfill_waste",
        "threw away 2 kg plastic",
        {"material_class": "plastic", "disposal_method": "landfill"},
    )
    recycling = _event(
        "waste",
        "recycling",
        "recycled 2 kg plastic",
        {"material_class": "plastic", "disposal_method": "recycling"},
    )
    landfill = landfill.model_copy(
        update={"quantities": QuantityNormalizer().normalize(landfill.raw_text, landfill)}
    )
    recycling = recycling.model_copy(
        update={"quantities": QuantityNormalizer().normalize(recycling.raw_text, recycling)}
    )

    landfill_build = WasteParameterBuilder().build(landfill)
    recycling_build = WasteParameterBuilder().build(recycling)
    resolver = CalculationIntentResolver()

    landfill_intent = resolver.resolve(landfill, landfill_build.parameters)[0]
    recycling_intent = resolver.resolve(recycling, recycling_build.parameters)[0]

    assert landfill_intent.activity_type == "landfill_waste"
    assert landfill_intent.semantic_dimensions["material_class"] == "plastic"
    assert landfill_intent.semantic_dimensions["disposal_method"] == "landfill"
    assert recycling_intent.semantic_dimensions["material_class"] == "plastic"
    assert recycling_intent.semantic_dimensions["disposal_method"] == "recycling"
    assert landfill_intent.unit_type == recycling_intent.unit_type == "Weight"


def test_specific_plastic_landfill_factor_wins_over_generic_and_wrong_method():
    pipeline = _pipeline_with_records(
        [
            _waste_record("fixture.waste.plastic_landfill", "Plastic waste landfill disposal"),
            _waste_record("fixture.waste.general_landfill", "Municipal solid waste landfill disposal"),
            _waste_record("fixture.waste.plastic_recycling", "Plastic waste recycling treatment"),
        ]
    )

    detail = pipeline.run("Threw away 2kg of plastic.").model_dump()["details"][0]

    assert detail["activity_type"] == "landfill_waste"
    assert detail["parameters"]["material_class"] == "plastic"
    assert detail["parameters"]["disposal_method"] == "landfill"
    assert detail["parameters"]["weight"] == 2
    assert detail["parameters"]["weight_unit"] == "kg"
    assert detail["factor"]["activity_id"] == "fixture.waste.plastic_landfill"
    assert detail["factor_diagnostics"]["intent_key"] == "waste.landfill.plastic.weight"
    assert any(
        rejection["activity_id"] == "fixture.waste.plastic_recycling"
        and "recycling method conflicts" in rejection["reason"]
        for rejection in detail["factor_diagnostics"]["top_rejections"]
    )


def test_generic_landfill_factor_used_only_after_specific_search_fails():
    pipeline = _pipeline_with_records(
        [
            _waste_record("fixture.waste.general_landfill", "Municipal solid waste landfill disposal"),
            _waste_record("fixture.waste.plastic_recycling", "Plastic waste recycling treatment"),
        ]
    )

    detail = pipeline.run("Threw away 2kg of plastic.").model_dump()["details"][0]

    assert detail["status"] == "estimated"
    assert detail["factor"]["activity_id"] == "fixture.waste.general_landfill"
    assert "waste.landfill.generic_fallback" in _assumption_codes(detail)
    diagnostics = detail["factor_diagnostics"]
    assert diagnostics["fallback_used"] is True
    assert diagnostics["selected_activity_id"] == "fixture.waste.general_landfill"
    assert [attempt["intent_key"] for attempt in diagnostics["attempts"]] == [
        "waste.landfill.plastic.weight",
        "waste.landfill.general_waste.weight",
    ]
    assert any(
        rejection["activity_id"] == "fixture.waste.plastic_recycling"
        and "recycling method conflicts" in rejection["reason"]
        for attempt in diagnostics["attempts"]
        for rejection in attempt["top_rejections"]
    )


def test_wrong_method_recycling_factor_never_satisfies_landfill_event():
    pipeline = _pipeline_with_records(
        [_waste_record("fixture.waste.plastic_recycling", "Plastic waste recycling treatment")]
    )

    detail = pipeline.run("Threw away 2kg of plastic.").model_dump()["details"][0]

    assert detail["factor"] is None
    assert detail["status"] == "fallback_estimated"
    assert "fallback_factor.waste.landfill_plastic" in _assumption_codes(detail)
    assert any(
        "recycling method conflicts" in rejection["reason"]
        for attempt in detail["factor_diagnostics"]["attempts"]
        for rejection in attempt["top_rejections"]
    )


def test_cross_domain_records_are_rejected_with_intents():
    resolver = CalculationIntentResolver()
    validator = FactorCompatibilityValidator()
    waste_event = _event(
        "waste",
        "landfill_waste",
        "threw away 2 kg plastic",
        {"material_class": "plastic", "disposal_method": "landfill"},
    )
    waste_event = waste_event.model_copy(
        update={"quantities": QuantityNormalizer().normalize(waste_event.raw_text, waste_event)}
    )
    waste_parameters = WasteParameterBuilder().build(waste_event).parameters
    waste_intent = resolver.resolve(waste_event, waste_parameters)[0]
    goods_event = _event(
        "goods_services",
        "food_purchase",
        "bought 1 kg beef",
        {"product_class": "beef"},
    )
    goods_parameters = {"product_class": "beef", "weight": 1, "weight_unit": "kg"}
    goods_intent = resolver.resolve(goods_event, goods_parameters)[0]

    assert not validator.validate_record(
        waste_event,
        waste_parameters,
        _goods_record("fixture.goods.beef_weight", "Beef food purchase by mass", "Weight"),
        intent=waste_intent,
    ).compatible
    assert not validator.validate_record(
        goods_event,
        goods_parameters,
        _waste_record("fixture.waste.plastic_landfill", "Plastic waste landfill disposal"),
        intent=goods_intent,
    ).compatible


def test_goods_factor_intents_select_weight_number_money_and_meal_records():
    records = [
        _goods_record("fixture.goods.beef_weight", "Beef food purchase by mass kg", "Weight"),
        _goods_record("fixture.goods.coffee_serving", "Coffee beverage serving cup", "Number"),
        _goods_record("fixture.goods.coffee_money", "Coffee beverage purchase spend USD", "Money"),
        _goods_record("fixture.goods.beef_burrito", "Beef burrito restaurant meal serving", "Number"),
    ]
    pipeline = _pipeline_with_records(records)

    beef = pipeline.run("Bought 1 kg of beef.").model_dump()["details"][0]
    coffees = pipeline.run("Bought two coffees.").model_dump()["details"][0]
    coffee_money = pipeline.run("Spent $6 on coffee.").model_dump()["details"][0]
    burrito = pipeline.run("Ordered a beef burrito.").model_dump()["details"][0]
    groceries = pipeline.run("Bought groceries.").model_dump()["details"][0]

    assert beef["factor"]["activity_id"] == "fixture.goods.beef_weight"
    assert beef["parameters"]["weight"] == 1
    assert coffees["factor"]["activity_id"] == "fixture.goods.coffee_serving"
    assert coffees["parameters"]["number"] == 2
    assert coffee_money["factor"]["activity_id"] == "fixture.goods.coffee_money"
    assert coffee_money["parameters"] == {"product_class": "coffee", "money": 6.0, "money_unit": "USD"}
    assert "number" not in coffee_money["parameters"]
    assert burrito["factor"]["activity_id"] == "fixture.goods.beef_burrito"
    assert groceries["status"] == "unresolved"
    assert groceries["factor_diagnostics"] is None


def test_api_pipeline_returns_plastic_landfill_intent_diagnostics(monkeypatch):
    pipeline = _pipeline_with_records(
        [
            _waste_record("fixture.waste.plastic_landfill", "Plastic waste landfill disposal"),
            _waste_record("fixture.waste.plastic_recycling", "Plastic waste recycling treatment"),
        ]
    )
    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: pipeline.run(journal).model_dump(by_alias=True),
    )
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post("/api/estimate-v2", json={"journal": "Threw away 2kg of plastic."})

    assert response.status_code == 200
    detail = response.json()["details"][0]
    assert detail["status"] == "estimated"
    assert detail["factor"]["activity_id"] == "fixture.waste.plastic_landfill"
    assert detail["factor_diagnostics"]["selected_activity_id"] == "fixture.waste.plastic_landfill"


def _pipeline_with_records(records):
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: records,
        remote_search=lambda *args, **kwargs: [],
    )
    return CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=_FakeClient(),
            factor_retriever=retriever,
        )
    )


class _FakeClient:
    def estimate(self, activity_id, parameters, selector_filters=None):
        amount = float(
            parameters.get("weight")
            or parameters.get("number")
            or parameters.get("money")
            or parameters.get("distance")
            or parameters.get("energy")
            or 1
        )
        return ClimatiqEstimate(co2e=round(amount * 0.5, 3), co2e_unit="kg", ok=True)


def _event(category, activity_type, raw_text, entities):
    return CarbonEvent(
        raw_text=raw_text,
        category=category,
        activity_type=activity_type,
        entities=entities,
        confidence=Confidence.from_score(0.8),
    )


def _waste_record(activity_id, name):
    return {
        "activity_id": activity_id,
        "name": name,
        "description": "End-of-life treatment by weight kg.",
        "sector": "Waste",
        "category": "Waste treatment",
        "unit_type": "Weight",
        "semantic_score": 1.0,
        "source_quality_score": 0.9,
    }


def _goods_record(activity_id, name, unit_type):
    return {
        "activity_id": activity_id,
        "name": name,
        "description": "Goods and services purchase emission factor.",
        "sector": "Goods",
        "category": "Food",
        "unit_type": unit_type,
        "semantic_score": 1.0,
        "source_quality_score": 0.9,
    }


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]
