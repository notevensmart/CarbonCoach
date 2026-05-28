import pytest

from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.pipeline import CarbonPipelineV2


class NoDatabaseFactorEstimator:
    """Forces the production fallback path without live Climatiq or search."""

    def estimate(self, event, parameters):
        return EmissionEstimateResult(ok=False, failure_status="unresolved")


@pytest.fixture(scope="module")
def fallback_pipeline():
    return CarbonPipelineV2(emission_estimator=NoDatabaseFactorEstimator())


GOODS_CASES = [
    *[
        (text, "coffee_purchase", "coffee")
        for text in [
            "Today I grabbed a takeaway coffee before work.",
            "I bought two coffees on the way home.",
            "After lunch I had 2 flat whites.",
            "I ordered one coffee at the cafe.",
            "This morning I picked up a coffee near the train station.",
        ]
    ],
    *[
        (text, "restaurant_meal", "burger")
        for text in [
            "For lunch I ordered a burger through Uber Eats.",
            "I bought two burgers for dinner.",
            "I had a hamburger after the movie.",
            "At the takeaway shop I got a burger.",
            "I grabbed one burger while out running errands.",
        ]
    ],
    *[
        (text, "restaurant_meal", "fries")
        for text in [
            "For lunch I ordered fries through Uber Eats.",
            "I bought two orders of fries.",
            "I had hot chips with dinner.",
            "At the takeaway shop I got fries.",
            "I grabbed one serving of fries after work.",
        ]
    ],
    *[
        (text, "restaurant_meal", "pizza")
        for text in [
            "I ordered a pizza for dinner.",
            "We bought two pizzas after work.",
            "I had pizza at the restaurant.",
            "I picked up one pizza from the takeaway place.",
            "I got a pizza through a delivery app.",
        ]
    ],
    *[
        (text, "restaurant_meal", "sandwich")
        for text in [
            "I bought a sandwich for lunch.",
            "I ordered two sandwiches at the cafe.",
            "I had a sandwich after training.",
            "I grabbed one sandwich from the deli.",
            "I picked up a sandwich on the way home.",
        ]
    ],
    *[
        (text, "restaurant_meal", "beef_burrito")
        for text in [
            "I ordered a beef burrito for lunch.",
            "I bought two beef burritos for dinner.",
            "I had a beef burrito through Uber Eats.",
            "I grabbed one beef burrito after class.",
            "I picked up a beef burrito from the takeaway shop.",
        ]
    ],
    *[
        (text, "food_purchase", "soft_drink")
        for text in [
            "I bought a soft drink with lunch.",
            "I ordered two soft drinks through Uber Eats.",
            "I grabbed one soda after work.",
            "I got a soft drink from the supermarket.",
            "I picked up a soft drink on the way home.",
        ]
    ],
    *[
        (text, "food_purchase", "milk")
        for text in [
            "I bought milk at the supermarket.",
            "I picked up one milk after work.",
            "I got milk for breakfast.",
            "I purchased two milks for the office.",
            "I grabbed milk while grocery shopping.",
        ]
    ],
    *[
        (text, "food_purchase", "bread")
        for text in [
            "I bought bread at the supermarket.",
            "I picked up one loaf of bread.",
            "I got bread for breakfast.",
            "I purchased two bread loaves for the week.",
            "I grabbed bread while grocery shopping.",
        ]
    ],
    *[
        (text, "food_purchase", "snacks")
        for text in [
            "I bought snacks at the supermarket.",
            "I picked up two snacks for the trip.",
            "I got a snack after work.",
            "I purchased chips for the party.",
            "I grabbed snacks while grocery shopping.",
        ]
    ],
]


WASTE_CASES = [
    *[
        (text, "landfill_waste", "plastic")
        for text in [
            "I threw away 2 kg of plastic waste.",
            "I discarded 500 g plastic bottles in the rubbish bin.",
            "I put 1 kg of plastic packaging in general waste.",
            "I disposed of 750 g of plastic in the trash bin.",
            "I threw away half a kilogram of plastic bottles.",
        ]
    ],
    *[
        (text, "landfill_waste", "food_waste")
        for text in [
            "I threw away 2 kg of food waste.",
            "I discarded 500 g of food scraps in general waste.",
            "I put 1 kg of leftover food in the rubbish bin.",
            "I disposed of 750 g organic waste in the trash bin.",
            "I threw away half a kilogram of food scraps.",
        ]
    ],
    *[
        (text, "landfill_waste", "cardboard")
        for text in [
            "I threw away 2 kg of cardboard.",
            "I discarded 500 g cardboard boxes in general waste.",
            "I put 1 kg of cardboard in the rubbish bin.",
            "I disposed of 750 g cardboard waste in the trash bin.",
            "I threw away half a kilogram of cardboard.",
        ]
    ],
    *[
        (text, "landfill_waste", "paper")
        for text in [
            "I threw away 2 kg of paper waste.",
            "I discarded 500 g paper in general waste.",
            "I put 1 kg of paper waste in the rubbish bin.",
            "I disposed of 750 g paper in the trash bin.",
            "I threw away half a kilogram of paper.",
        ]
    ],
    *[
        (text, "landfill_waste", "mixed_packaging")
        for text in [
            "I threw away 2 kg of mixed packaging.",
            "I discarded 500 g of food packaging in general waste.",
            "I put 1 kg packaging waste in the rubbish bin.",
            "I disposed of 750 g wrappers in the trash bin.",
            "I threw away half a kilogram of mixed packaging.",
        ]
    ],
    *[
        (text, "recycling", "plastic")
        for text in [
            "I recycled 500 g of plastic bottles.",
            "I put 1 kg plastic in the recycling bin.",
            "I recycled half a kilogram of plastic packaging.",
            "I recycled 2 kg plastic waste after dinner.",
            "I put 750 g plastic bottles out for recycling.",
        ]
    ],
    *[
        (text, "recycling", "cardboard")
        for text in [
            "I recycled 500 g of cardboard.",
            "I put 1 kg cardboard boxes in the recycling bin.",
            "I recycled half a kilogram of cardboard packaging.",
            "I recycled 2 kg cardboard after unpacking deliveries.",
            "I put 750 g cardboard out for recycling.",
        ]
    ],
    *[
        (text, "recycling", "paper")
        for text in [
            "I recycled 500 g of paper.",
            "I put 1 kg paper waste in the recycling bin.",
            "I recycled half a kilogram of paper.",
            "I recycled 2 kg paper after cleaning my desk.",
            "I put 750 g paper out for recycling.",
        ]
    ],
    *[
        (text, "recycling", material)
        for text, material in [
            ("I recycled 500 g of glass bottles.", "glass"),
            ("I put 1 kg glass in the recycling bin.", "glass"),
            ("I recycled 750 g aluminium cans.", "metal"),
            ("I put 500 g metal cans out for recycling.", "metal"),
            ("I recycled 1 kg steel can waste.", "metal"),
        ]
    ],
    *[
        (text, "composting", "food_waste")
        for text in [
            "I composted 2 kg of food scraps.",
            "I put 500 g food waste in the compost bin.",
            "I composted half a kilogram of organic waste.",
            "I put 1 kg leftover food into compost.",
            "I composted 750 g food scraps after dinner.",
        ]
    ],
]


STRESS_CASES = [
    *[
        pytest.param(text, activity_type, {"product_class": product_class}, id=f"goods-{index:02d}-{product_class}")
        for index, (text, activity_type, product_class) in enumerate(GOODS_CASES, start=1)
    ],
    *[
        pytest.param(text, activity_type, {"material_class": material_class}, id=f"waste-{index:02d}-{material_class}")
        for index, (text, activity_type, material_class) in enumerate(WASTE_CASES, start=1)
    ],
]


def test_stress_suite_has_exactly_100_goods_and_waste_cases():
    assert len(STRESS_CASES) == 100


@pytest.mark.parametrize(("journal", "activity_type", "expected_parameters"), STRESS_CASES)
def test_common_goods_and_waste_inputs_are_estimated_through_maintained_pathways(
    fallback_pipeline,
    journal,
    activity_type,
    expected_parameters,
):
    result = fallback_pipeline.run(journal).model_dump()
    detail = _matching_detail(result["details"], activity_type, expected_parameters)

    assert detail is not None, result["details"]
    assert detail["status"] == "fallback_estimated"
    assert detail["co2e"] is not None
    assert detail["source"] == "fallback"
    assert any(
        assumption["code"].startswith("fallback_factor.")
        for assumption in detail["assumptions"]
    )


def test_stress_multi_material_waste_sentence_splits_into_estimable_events(fallback_pipeline):
    result = fallback_pipeline.run(
        "After dinner I threw away 2 kg plastic waste and 2kg food waste, "
        "then recycled 500 g cardboard and 250 g glass bottles."
    ).model_dump()

    represented = [
        (detail["activity_type"], detail["parameters"].get("material_class"), detail["status"])
        for detail in result["details"]
    ]

    assert represented == [
        ("landfill_waste", "plastic", "fallback_estimated"),
        ("landfill_waste", "food_waste", "fallback_estimated"),
        ("recycling", "cardboard", "fallback_estimated"),
        ("recycling", "glass", "fallback_estimated"),
    ]
    assert result["coverage"]["estimate_is_partial"] is False


def test_stress_shopping_list_sentence_keeps_each_common_item(fallback_pipeline):
    result = fallback_pipeline.run(
        "Today I ordered a burger and fries through Uber Eats, then bought milk, bread, and snacks."
    ).model_dump()

    represented = [
        (detail["activity_type"], detail["parameters"].get("product_class"), detail["status"])
        for detail in result["details"]
    ]

    assert represented == [
        ("restaurant_meal", "burger", "fallback_estimated"),
        ("restaurant_meal", "fries", "fallback_estimated"),
        ("food_purchase", "milk", "fallback_estimated"),
        ("food_purchase", "bread", "fallback_estimated"),
        ("food_purchase", "snacks", "fallback_estimated"),
    ]
    assert all(
        "goods_services.delivery_transport.not_included"
        in [issue["code"] for issue in detail["issues"]]
        for detail in result["details"][:2]
    )


def test_stress_user_reported_journal_keeps_common_goods_and_weighted_waste(
    fallback_pipeline,
):
    result = fallback_pipeline.run(
        "Today I drove 18 km to uni and grabbed a takeaway coffee on the way. "
        "For lunch I ordered a burger and fries through Uber Eats, then stopped by "
        "the supermarket to buy milk, bread, and snacks. After getting home I used "
        "the heater for about 3 hours while watching YouTube and gaming on my PC. "
        "Later I did one load of laundry, charged my phone overnight, and threw away "
        "2kg plastic waste and 2kg food waste."
    ).model_dump()

    represented = [
        (
            detail["activity_type"],
            detail["parameters"].get("product_class")
            or detail["parameters"].get("material_class"),
            detail["status"],
        )
        for detail in result["details"]
        if detail["category"] in {"goods_services", "waste"}
    ]

    assert represented == [
        ("coffee_purchase", "coffee", "fallback_estimated"),
        ("restaurant_meal", "burger", "fallback_estimated"),
        ("restaurant_meal", "fries", "fallback_estimated"),
        ("food_purchase", "milk", "fallback_estimated"),
        ("food_purchase", "bread", "fallback_estimated"),
        ("food_purchase", "snacks", "fallback_estimated"),
        ("landfill_waste", "plastic", "fallback_estimated"),
        ("landfill_waste", "food_waste", "fallback_estimated"),
    ]
    assert [
        detail["parameters"].get("weight")
        for detail in result["details"]
        if detail["category"] == "waste"
    ] == [2.0, 2.0]


def _matching_detail(details, activity_type, expected_parameters):
    for detail in details:
        if detail["activity_type"] != activity_type:
            continue
        parameters = detail["parameters"]
        if all(parameters.get(key) == value for key, value in expected_parameters.items()):
            return detail
    return None
