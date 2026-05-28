import json

import pytest

from app.domain.factor_metadata_overlay import (
    DEFAULT_OVERLAY_PATH,
    KNOWN_UNIT_TYPES,
    SUPPORTED_CATEGORIES,
    EnrichedFactorMetadataRow,
    load_enriched_metadata_overlay,
    merge_enriched_factor_metadata,
)
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.services.climatiq_api import ClimatiqEstimate


def test_default_overlay_schema_is_valid_source_noted_and_category_limited():
    overlay = load_enriched_metadata_overlay(DEFAULT_OVERLAY_PATH, required=True)
    rows = overlay.rows

    assert 30 <= len(rows) <= 60
    assert {row.carboncoach_category for row in rows} <= SUPPORTED_CATEGORIES
    assert "food" not in {row.carboncoach_category for row in rows}
    assert {row.unit_type for row in rows} <= KNOWN_UNIT_TYPES
    assert all(row.description.strip() for row in rows)
    assert all(row.source_note.strip() for row in rows)
    assert all(0.0 <= row.source_quality_score <= 1.0 for row in rows)
    assert all(row.preferred_terms for row in rows)


def test_overlay_rejects_unknown_controlled_values():
    with pytest.raises(ValueError, match="unknown unit_type"):
        EnrichedFactorMetadataRow.model_validate(
            {
                "activity_id": "fixture.invalid",
                "description": "Invalid unit.",
                "carboncoach_category": "waste",
                "allowed_activity_types": ["landfill_waste"],
                "unit_type": "Bananas",
                "preferred_terms": ["waste"],
                "semantic_dimensions": {"material_classes": ["plastic"]},
                "calculation_boundary": "Invalid unit test.",
                "source_note": "Fixture.",
                "source_quality_score": 0.5,
            }
        )

    with pytest.raises(ValueError, match="material_classes has unknown values"):
        EnrichedFactorMetadataRow.model_validate(
            {
                "activity_id": "fixture.invalid",
                "description": "Invalid material.",
                "carboncoach_category": "waste",
                "allowed_activity_types": ["landfill_waste"],
                "unit_type": "Weight",
                "preferred_terms": ["waste"],
                "semantic_dimensions": {"material_classes": ["banana_peel"]},
                "calculation_boundary": "Invalid material test.",
                "source_note": "Fixture.",
                "source_quality_score": 0.5,
            }
        )


def test_duplicate_activity_ids_are_rejected_unless_explicitly_allowed(tmp_path):
    row = {
        "activity_id": "fixture.duplicate",
        "description": "Duplicate fixture.",
        "carboncoach_category": "waste",
        "allowed_activity_types": ["landfill_waste"],
        "unit_type": "Weight",
        "preferred_terms": ["waste", "landfill"],
        "semantic_dimensions": {
            "material_classes": ["general_waste"],
            "disposal_methods": ["landfill"],
        },
        "calculation_boundary": "Fixture boundary.",
        "source_note": "Fixture source.",
        "source_quality_score": 0.5,
    }
    path = tmp_path / "overlay.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate enriched metadata activity_id"):
        load_enriched_metadata_overlay(path, required=True)


def test_overlay_merge_is_copy_on_write_and_missing_file_degrades_safely(tmp_path):
    raw_metadata = {
        "carboncoach.overlay.waste.plastic_landfill.weight": {
            "activity_id": "carboncoach.overlay.waste.plastic_landfill.weight",
            "name": "Shallow waste factor",
            "sector": "Waste",
            "category": "Waste treatment",
            "unit_type": "Weight",
        },
        "fixture.raw.only": {
            "activity_id": "fixture.raw.only",
            "name": "Raw only",
            "sector": "Energy",
            "category": "Electricity",
            "unit_type": "Energy",
        },
    }
    original = {key: dict(value) for key, value in raw_metadata.items()}

    merged = merge_enriched_factor_metadata(raw_metadata)

    assert raw_metadata == original
    assert merged is not raw_metadata
    assert "preferred_terms" in merged["carboncoach.overlay.waste.plastic_landfill.weight"]
    assert merged["fixture.raw.only"] == raw_metadata["fixture.raw.only"]
    assert merged["fixture.raw.only"] is not raw_metadata["fixture.raw.only"]
    missing = merge_enriched_factor_metadata(
        raw_metadata,
        overlay_path=tmp_path / "missing.jsonl",
    )
    assert missing == raw_metadata


def test_pathway_key_rows_merge_only_when_explicitly_marked_local_fallback(tmp_path):
    row = {
        "fallback_pathway_key": "fixture.local.pathway",
        "local_fallback": True,
        "description": "Local fallback pathway.",
        "carboncoach_category": "waste",
        "allowed_activity_types": ["landfill_waste"],
        "unit_type": "Weight",
        "preferred_terms": ["general waste", "landfill"],
        "semantic_dimensions": {
            "material_classes": ["general_waste"],
            "disposal_methods": ["landfill"],
        },
        "calculation_boundary": "Fixture fallback boundary.",
        "source_note": "Fixture source.",
        "source_quality_score": 0.5,
    }
    path = tmp_path / "overlay.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    raw = {
        "fixture.raw": {
            "activity_id": "fixture.raw",
            "name": "Raw fallback row",
            "sector": "Waste",
            "category": "Waste",
            "unit_type": "Weight",
            "fallback_pathway_key": "fixture.local.pathway",
        }
    }

    merged = merge_enriched_factor_metadata(
        raw,
        overlay=load_enriched_metadata_overlay(path, required=True),
    )

    assert merged["fixture.raw"]["local_fallback"] is True
    assert merged["fixture.raw"]["carboncoach_pathway_key"] == "fixture.local.pathway"


def test_enriched_metadata_improves_specific_waste_ranking_over_shallow_raw_records():
    raw_records = [
        _record("carboncoach.overlay.waste.plastic_landfill.weight", "Pathway A", "Waste", "Waste", "Weight"),
        _record(
            "carboncoach.overlay.waste.general_landfill.weight",
            "Municipal solid waste landfill disposal",
            "Waste",
            "Waste treatment",
            "Weight",
        ),
        _record(
            "carboncoach.overlay.waste.plastic_recycling.weight",
            "Plastic waste recycling treatment",
            "Waste",
            "Waste treatment",
            "Weight",
        ),
    ]

    raw_detail = _pipeline_with_records(raw_records).run(
        "Threw away 2kg of plastic."
    ).model_dump()["details"][0]
    enriched_detail = _pipeline_with_records(_merge_records(raw_records)).run(
        "Threw away 2kg of plastic."
    ).model_dump()["details"][0]

    assert raw_detail["factor"]["activity_id"] == "carboncoach.overlay.waste.plastic_landfill.weight"
    assert enriched_detail["factor"]["activity_id"] == "carboncoach.overlay.waste.plastic_landfill.weight"
    assert enriched_detail["factor"]["score"] > raw_detail["factor"]["score"]
    assert "waste.landfill.generic_fallback" not in _assumption_codes(enriched_detail)
    assert any(
        "source_quality_score from enriched factor metadata" in reason
        for reason in enriched_detail["factor"]["match_reasons"]
    )


@pytest.mark.parametrize(
    ("journal", "activity_id"),
    [
        ("Threw away 2kg of plastic.", "carboncoach.overlay.waste.plastic_landfill.weight"),
        ("Discarded 2 kg of plastic packaging.", "carboncoach.overlay.waste.plastic_landfill.weight"),
        ("Recycled 500 g of plastic bottles.", "carboncoach.overlay.waste.plastic_recycling.weight"),
        ("Composted 2 kg of food scraps.", "carboncoach.overlay.waste.food_composting.weight"),
        ("Bought 1 kg of beef.", "carboncoach.overlay.goods.beef_weight.weight"),
        ("Bought two coffees.", "carboncoach.overlay.goods.coffee_serving.number"),
        ("Spent $6 on coffee.", "carboncoach.overlay.goods.coffee_spend.money"),
        ("Ordered a beef burrito.", "carboncoach.overlay.goods.beef_burrito_serving.number"),
        ("Ran a 2 kW heater for 3 hours.", "carboncoach.overlay.energy.space_heater.kwh"),
        ("Drove 12 km in a petrol car.", "carboncoach.overlay.transport.petrol_car.distance"),
    ],
)
def test_common_pathway_retrieval_uses_enriched_metadata(journal, activity_id):
    detail = _pipeline_with_records(_merge_records(_common_records())).run(journal).model_dump()["details"][0]

    assert detail["status"] == "estimated"
    assert detail["factor"]["activity_id"] == activity_id


def test_money_and_number_coffee_pathways_do_not_cross_select():
    pipeline = _pipeline_with_records(
        _merge_records(
            [
                _record(
                    "carboncoach.overlay.goods.coffee_serving.number",
                    "Coffee fixture A",
                    "Goods",
                    "Food",
                    "Number",
                ),
                _record(
                    "carboncoach.overlay.goods.coffee_spend.money",
                    "Coffee fixture B",
                    "Goods",
                    "Food",
                    "Money",
                ),
            ]
        )
    )

    count_detail = pipeline.run("Bought two coffees.").model_dump()["details"][0]
    money_detail = pipeline.run("Spent $6 on coffee.").model_dump()["details"][0]

    assert count_detail["factor"]["unit_type"] == "Number"
    assert count_detail["factor"]["activity_id"] == "carboncoach.overlay.goods.coffee_serving.number"
    assert money_detail["factor"]["unit_type"] == "Money"
    assert money_detail["factor"]["activity_id"] == "carboncoach.overlay.goods.coffee_spend.money"
    assert "number" not in money_detail["parameters"]


def test_multi_activity_overlay_stress_keeps_partial_results_visible_and_suppresses_comparison():
    records = _merge_records(
        [
            _record(
                "carboncoach.overlay.transport.petrol_car.distance",
                "Transport fixture",
                "Transport",
                "Vehicles",
                "Distance",
            ),
            _record(
                "carboncoach.overlay.goods.coffee_serving.number",
                "Coffee fixture",
                "Goods",
                "Food",
                "Number",
            ),
            _record(
                "carboncoach.overlay.goods.beef_burrito_serving.number",
                "Burrito fixture",
                "Goods",
                "Food",
                "Number",
            ),
            _record(
                "carboncoach.overlay.waste.plastic_recycling.weight",
                "Recycling fixture",
                "Waste",
                "Waste treatment",
                "Weight",
            ),
            _record(
                "carboncoach.overlay.waste.food_landfill.weight",
                "Food waste fixture",
                "Waste",
                "Waste treatment",
                "Weight",
            ),
        ]
    )

    result = _pipeline_with_records(records).run(
        "I drove 12 km, bought two coffees, ordered a beef burrito, "
        "recycled 500 g of plastic bottles, threw away 1 kg of food waste, "
        "and bought groceries."
    ).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == [
        "car_ride",
        "coffee_purchase",
        "restaurant_meal",
        "recycling",
        "landfill_waste",
        "food_purchase",
    ]
    assert {detail["category"] for detail in result["details"]} == {
        "transport",
        "goods_services",
        "waste",
    }
    assert [detail["status"] for detail in result["details"][:-1]] == ["estimated"] * 5
    assert result["details"][-1]["status"] == "unresolved"
    assert result["coverage"]["estimate_is_partial"] is True
    assert result["comparison"] is None


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


def _merge_records(records):
    raw = {record["activity_id"]: record for record in records}
    return list(merge_enriched_factor_metadata(raw).values())


def _common_records():
    return [
        _record("carboncoach.overlay.waste.plastic_landfill.weight", "Waste fixture A", "Waste", "Waste treatment", "Weight"),
        _record("carboncoach.overlay.waste.plastic_recycling.weight", "Waste fixture B", "Waste", "Waste treatment", "Weight"),
        _record("carboncoach.overlay.waste.food_composting.weight", "Waste fixture C", "Waste", "Waste treatment", "Weight"),
        _record("carboncoach.overlay.goods.beef_weight.weight", "Goods fixture A", "Goods", "Food", "Weight"),
        _record("carboncoach.overlay.goods.coffee_serving.number", "Goods fixture B", "Goods", "Food", "Number"),
        _record("carboncoach.overlay.goods.coffee_spend.money", "Goods fixture C", "Goods", "Food", "Money"),
        _record("carboncoach.overlay.goods.beef_burrito_serving.number", "Goods fixture D", "Goods", "Food", "Number"),
        _record("carboncoach.overlay.energy.space_heater.kwh", "Energy fixture A", "Energy", "Electricity", "Energy"),
        _record("carboncoach.overlay.transport.petrol_car.distance", "Transport fixture A", "Transport", "Vehicles", "Distance"),
    ]


def _record(activity_id, name, sector, category, unit_type):
    return {
        "activity_id": activity_id,
        "name": name,
        "sector": sector,
        "category": category,
        "unit_type": unit_type,
    }


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]
