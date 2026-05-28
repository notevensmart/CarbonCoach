from __future__ import annotations

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.assumptions import generic_waste_fallback_assumption
from app.domain.factor_intents import FactorIntent
from app.domain.material_ontology import ontology_terms
from app.domain.models import CarbonEvent


class CalculationIntentResolver:
    """Resolves validated events and parameters into database factor intents."""

    def resolve(self, event: CarbonEvent, parameters: dict) -> list[FactorIntent]:
        if event.category == "waste":
            return self._waste_intents(event, parameters)
        if event.category == "goods_services":
            return self._goods_services_intents(event, parameters)
        return self._generic_intents(event, parameters)

    def _waste_intents(self, event: CarbonEvent, parameters: dict) -> list[FactorIntent]:
        if "weight" not in parameters or parameters.get("weight_unit") != "kg":
            return []
        disposal_method = _clean(parameters.get("disposal_method"))
        material_class = _clean(parameters.get("material_class")) or "unknown"
        if not disposal_method or disposal_method == "unknown":
            return []

        intents: list[FactorIntent] = []
        if material_class not in {"", "unknown", "mixed"}:
            intents.append(
                self._waste_intent(
                    event,
                    parameters,
                    disposal_method=disposal_method,
                    material_class=material_class,
                    strict_material=True,
                )
            )

        if disposal_method == "landfill" and material_class not in {
            "",
            "unknown",
            "general_waste",
        }:
            intents.append(
                self._waste_intent(
                    event,
                    parameters,
                    disposal_method=disposal_method,
                    material_class="general_waste",
                    strict_material=True,
                    fallback_for_material=material_class,
                )
            )

        if not intents:
            intents.append(
                self._waste_intent(
                    event,
                    parameters,
                    disposal_method=disposal_method,
                    material_class=material_class or "general_waste",
                    strict_material=False,
                )
            )
        return intents

    def _waste_intent(
        self,
        event: CarbonEvent,
        parameters: dict,
        *,
        disposal_method: str,
        material_class: str,
        strict_material: bool,
        fallback_for_material: str | None = None,
    ) -> FactorIntent:
        required_parameters = {
            "weight": parameters["weight"],
            "weight_unit": parameters["weight_unit"],
        }
        method_terms = ontology_terms(disposal_method)
        material_terms = ontology_terms(material_class)
        base_terms = [
            material_class.replace("_", " "),
            "waste",
            disposal_method,
            "disposal",
            "end of life",
            "treatment",
            "by weight",
            "kg",
        ]
        hard_constraints = {
            "unit_type": "Weight",
            "category_family": "waste",
            "disposal_method": disposal_method,
        }
        if strict_material:
            hard_constraints["material_class"] = material_class
        semantic_dimensions = {
            "disposal_method": disposal_method,
            "material_class": material_class,
        }
        if fallback_for_material:
            semantic_dimensions["generic_fallback_for_material"] = fallback_for_material

        fallback_strategy = [
            "same_method_same_material",
            "same_method_general_waste",
            "maintained_local_fallback",
        ]
        assumption = (
            generic_waste_fallback_assumption(fallback_for_material, disposal_method)
            if fallback_for_material
            else None
        )
        return FactorIntent(
            intent_key=(
                f"waste.{disposal_method}.{material_class}.weight"
                if not fallback_for_material
                else f"waste.{disposal_method}.general_waste.weight"
            ),
            category=event.category,
            activity_type=event.activity_type,
            unit_type="Weight",
            required_parameters=required_parameters,
            semantic_dimensions=semantic_dimensions,
            hard_constraints=hard_constraints,
            preferred_terms=list(dict.fromkeys([*base_terms, *material_terms, *method_terms])),
            excluded_terms=_excluded_waste_method_terms(disposal_method),
            search_query=" ".join(
                dict.fromkeys([*base_terms, *material_terms, *method_terms])
            ),
            selector_filters={"unit_type": "Weight", "sector": "Waste"},
            fallback_strategy=fallback_strategy,
            assumption_if_generic_fallback_used=assumption,
        )

    def _goods_services_intents(
        self,
        event: CarbonEvent,
        parameters: dict,
    ) -> list[FactorIntent]:
        unit_type = _unit_type_from_parameters(parameters)
        if unit_type is None:
            return []
        product_class = _clean(parameters.get("product_class")) or _clean(
            event.entities.get("product_class")
        )
        if not product_class:
            return []

        required_parameters = _required_parameters_for_unit(parameters, unit_type)
        if not required_parameters:
            return []

        product_label = product_class.replace("_", " ")
        category_terms = {
            "coffee_purchase": ["coffee", "beverage", "serving", "cup"],
            "restaurant_meal": ["restaurant meal", "meal", "serving", product_label],
            "food_purchase": ["food", "purchase", product_label],
        }.get(event.activity_type, [product_label, "purchase"])
        unit_terms = {
            "Weight": ["by weight", "kg", "mass"],
            "Number": ["serving", "item", "count"],
            "Money": ["spend", "money", "usd", "purchase price"],
        }[unit_type]
        terms = list(dict.fromkeys([product_label, *category_terms, *unit_terms]))
        return [
            FactorIntent(
                intent_key=(
                    f"goods_services.{event.activity_type}.{product_class}."
                    f"{unit_type.lower()}"
                ),
                category=event.category,
                activity_type=event.activity_type,
                unit_type=unit_type,
                required_parameters=required_parameters,
                semantic_dimensions={"product_class": product_class},
                hard_constraints={
                    "unit_type": unit_type,
                    "category_family": "goods_services",
                    "product_class": product_class,
                },
                preferred_terms=terms,
                excluded_terms=_excluded_goods_terms(product_class),
                search_query=" ".join(terms),
                selector_filters={"unit_type": unit_type, "sector": "Goods"},
                fallback_strategy=[
                    "same_product_same_unit",
                    "compatible_category_broader_product",
                    "maintained_local_fallback",
                ],
            )
        ]

    def _generic_intents(self, event: CarbonEvent, parameters: dict) -> list[FactorIntent]:
        unit_type = _unit_type_from_parameters(parameters, event.activity_type)
        if unit_type is None:
            return []
        required_parameters = _required_parameters_for_unit(parameters, unit_type)
        if not required_parameters:
            return []
        metadata = ACTIVITY_TAXONOMY.get(event.activity_type, {})
        semantic_dimensions = {
            str(field): str(parameters[field])
            for field in (
                *metadata.get("factor_identity_fields", ()),
                *metadata.get("factor_trait_fields", ()),
            )
            if parameters.get(field) is not None
        }
        terms = [
            str(metadata.get("climatiq_factor_query") or event.activity_type),
            *[str(term) for term in metadata.get("factor_match_terms", ())],
            *[str(term) for term in metadata.get("factor_preferred_terms", ())],
            *semantic_dimensions.values(),
            unit_type,
        ]
        return [
            FactorIntent(
                intent_key=f"{event.category}.{event.activity_type}.{unit_type.lower()}",
                category=event.category,
                activity_type=event.activity_type,
                unit_type=unit_type,
                required_parameters=required_parameters,
                semantic_dimensions=semantic_dimensions,
                hard_constraints={
                    "unit_type": unit_type,
                    "category_family": event.category,
                },
                preferred_terms=list(dict.fromkeys(term for term in terms if term)),
                excluded_terms=[
                    str(term) for term in metadata.get("factor_excluded_terms", ())
                ],
                search_query=" ".join(dict.fromkeys(term for term in terms if term)),
                selector_filters={
                    "unit_type": unit_type,
                    "sector": _sector_for_category(event.category),
                },
                fallback_strategy=["compatible_database_factor", "maintained_local_fallback"],
            )
        ]


def _unit_type_from_parameters(
    parameters: dict,
    activity_type: str | None = None,
) -> str | None:
    if "energy" in parameters and parameters.get("energy_unit") == "kWh":
        return "Energy"
    if "money" in parameters and parameters.get("money_unit"):
        return "Money"
    if "number" in parameters and parameters.get("number_unit") == "item":
        return "Number"
    if "weight" in parameters and parameters.get("weight_unit") == "kg":
        return "Weight"
    if "distance" in parameters and parameters.get("distance_unit") == "km":
        if activity_type:
            compatible_units = tuple(
                ACTIVITY_TAXONOMY.get(activity_type, {}).get("compatible_unit_types", ())
            )
            if "PassengerOverDistance" in compatible_units:
                return "PassengerOverDistance"
        return "PassengerOverDistance" if parameters.get("passengers") else "Distance"
    return None


def _required_parameters_for_unit(parameters: dict, unit_type: str) -> dict:
    keys_by_unit = {
        "Energy": ("energy", "energy_unit"),
        "Distance": ("distance", "distance_unit"),
        "PassengerOverDistance": ("distance", "distance_unit"),
        "Weight": ("weight", "weight_unit"),
        "Number": ("number", "number_unit"),
        "Money": ("money", "money_unit"),
    }
    keys = keys_by_unit[unit_type]
    return {key: parameters[key] for key in keys if key in parameters}


def _excluded_waste_method_terms(disposal_method: str) -> list[str]:
    excluded = []
    for method in ("landfill", "recycling", "composting", "incineration"):
        if method != disposal_method:
            excluded.extend(ontology_terms(method))
    return list(dict.fromkeys(excluded))


def _excluded_goods_terms(product_class: str) -> list[str]:
    product_conflicts = {
        "coffee": ("beef", "burrito", "groceries"),
        "beef": ("coffee", "burrito"),
        "beef_burrito": ("coffee", "groceries"),
        "groceries": ("coffee", "burrito", "beef"),
    }
    return list(product_conflicts.get(product_class, ()))


def _sector_for_category(category: str) -> str:
    return {
        "energy": "Energy",
        "transport": "Transport",
        "goods_services": "Goods",
        "waste": "Waste",
    }[category]


def _clean(value: object) -> str:
    return str(value or "").strip().lower()
