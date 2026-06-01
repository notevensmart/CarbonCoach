from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.activity_taxonomy import GOODS_SERVICES_TAXONOMY, TRANSPORT_TAXONOMY, WASTE_TAXONOMY
from app.domain.assumptions import (
    SPACE_HEATER_DEFAULT_POWER_KW,
    distance_compact_k_context_assumption,
    default_au_electricity_region_assumption,
    flight_default_factor_assumption,
    singular_item_count_assumption,
    space_heater_default_power_assumption,
)
from app.domain.models import Assumption, CarbonEvent, Confidence, EstimateStatus, Issue, Quantity


@dataclass(frozen=True)
class ParameterBuildResult:
    parameters: dict
    confidence: Confidence
    assumptions: list[Assumption] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    can_estimate: bool = True
    status: EstimateStatus | None = None


class EnergyParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        energy = _first_quantity(event.quantities, "energy")
        power = _first_quantity(event.quantities, "power")
        duration = _first_quantity(event.quantities, "duration")
        region_parameters = _energy_region_parameters(event)
        assumptions = [] if region_parameters else [default_au_electricity_region_assumption()]

        if event.activity_type in {
            "natural_gas_use",
            "cooking_appliance_use",
            "hot_water_use",
        }:
            parameters = {}
            if duration is not None:
                parameters.update(
                    {
                        "duration": _round_quantity(duration.value),
                        "duration_unit": "hours",
                    }
                )
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.30),
                assumptions=[],
                issues=[
                    Issue(
                        code=f"energy.{event.activity_type}.unsupported_factor",
                        message=(
                            f"Detected {event.activity_type}, but no validated V2 "
                            "parameter and factor pathway is configured for it yet."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if event.activity_type == "generic_energy_use":
            parameters = {"device": _entity_text(event.entities.get("device")) or "unknown"}
            if duration is not None:
                parameters.update(
                    {
                        "duration": _round_quantity(duration.value),
                        "duration_unit": "hours",
                    }
                )
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.20),
                assumptions=[],
                issues=[
                    Issue(
                        code="energy.activity.unspecified",
                        message=(
                            "Detected possible device use, but the device and required "
                            "energy information are too ambiguous to estimate safely."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if (
            event.activity_type == "space_heater_use"
            and event.entities.get("power_source") == "natural_gas"
        ):
            parameters = {}
            if duration is not None:
                parameters = {
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                    "power_source": "natural_gas",
                }
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.35),
                assumptions=[],
                issues=[
                    Issue(
                        code="energy.natural_gas_heater.unsupported_factor",
                        message=(
                            "Detected a gas heater, but no validated natural-gas "
                            "heater factor pathway is configured in V2 yet."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if energy is not None:
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy.value),
                    "energy_unit": "kWh",
                    **region_parameters,
                },
                confidence=Confidence.from_score(0.95),
                assumptions=assumptions,
            )

        if power is not None and duration is not None:
            energy_kwh = power.value * duration.value
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy_kwh),
                    "energy_unit": "kWh",
                    "power": _round_quantity(power.value),
                    "power_unit": "kW",
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                    **region_parameters,
                },
                confidence=Confidence.from_score(0.90),
                assumptions=assumptions,
            )

        if event.activity_type == "space_heater_use" and duration is not None:
            power_kw = SPACE_HEATER_DEFAULT_POWER_KW
            energy_kwh = power_kw * duration.value
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy_kwh),
                    "energy_unit": "kWh",
                    "power": power_kw,
                    "power_unit": "kW",
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                    **region_parameters,
                },
                confidence=Confidence.from_score(0.60),
                assumptions=[
                    space_heater_default_power_assumption(),
                    *assumptions,
                ],
            )

        if duration is not None:
            return ParameterBuildResult(
                parameters={
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                },
                confidence=Confidence.from_score(0.30),
                assumptions=[],
                issues=[
                    Issue(
                        code="energy.appliance.default_power_unavailable",
                        message=(
                            "Detected appliance usage duration, but no validated "
                            "default-power conversion is configured for this appliance."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        return ParameterBuildResult(
            parameters=region_parameters,
            confidence=Confidence.from_score(0.25),
            assumptions=assumptions,
            issues=[
                Issue(
                    code="energy.missing_quantity",
                    message="Could not find an energy amount, duration, or power needed for this energy estimate.",
                    severity="warning",
                )
            ],
            can_estimate=False,
        )


class TransportParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        distance = _first_quantity(event.quantities, "distance")
        if distance is None:
            parameters = {"transport_mode": event.activity_type}
            _add_geospatial_transport_parameters(parameters, event)
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.25),
                issues=[
                    Issue(
                        code="transport.missing_distance",
                        message="Could not find a distance needed for this transport estimate.",
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        metadata = TRANSPORT_TAXONOMY[event.activity_type]
        policy = str(metadata.get("estimate_policy", "unresolved"))
        assumptions = []
        if _is_compact_k_distance(distance):
            assumptions.append(distance_compact_k_context_assumption(distance.surface or "k"))
        parameters = {
            "distance": _round_quantity(distance.value),
            "distance_unit": "km",
            "transport_mode": event.activity_type,
        }
        _add_geospatial_transport_parameters(parameters, event)
        _add_declared_transport_traits(parameters, event, metadata)
        if event.activity_type == "flight":
            _add_flight_factor_defaults(parameters, event, distance, assumptions)

        if policy == "operational_zero":
            parameters["emissions_boundary"] = metadata["emissions_boundary"]
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(_distance_confidence(event, distance)),
                assumptions=assumptions,
                status="not_estimated",
            )

        if policy == "unresolved":
            issue_code = (
                "transport.flight.factor_unresolved"
                if event.activity_type == "flight"
                else "transport.mode.unsupported"
            )
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.30),
                assumptions=assumptions,
                issues=[
                    Issue(
                        code=issue_code,
                        message=(
                            f"Detected {event.activity_type}, but no approved Climatiq "
                            "factor pathway is configured for this mode yet."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if policy == "climatiq_distance":
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(
                    0.60
                    if event.activity_type == "flight"
                    else _distance_confidence(event, distance)
                ),
                assumptions=assumptions,
            )

        vehicle_type = _entity_text(event.entities.get("vehicle_type")) or "car"
        vehicle_size = _entity_text(event.entities.get("vehicle_size")) or "medium"
        fuel_type = _entity_text(event.entities.get("fuel_type")) or "petrol"

        parameters.update({
            "vehicle_type": vehicle_type,
            "vehicle_size": vehicle_size,
            "fuel_type": fuel_type,
        })
        if event.entities.get("vehicle_make"):
            parameters["vehicle_make"] = event.entities["vehicle_make"]
        if event.entities.get("vehicle_model"):
            parameters["vehicle_model"] = event.entities["vehicle_model"]
        if event.entities.get("vehicle_class"):
            parameters["vehicle_class"] = event.entities["vehicle_class"]
        if event.entities.get("vehicle_description"):
            parameters["vehicle_description"] = event.entities["vehicle_description"]
        if event.entities.get("vehicle_metadata_record_id"):
            parameters["vehicle_metadata_record_id"] = event.entities["vehicle_metadata_record_id"]
        if event.entities.get("vehicle_metadata_source"):
            parameters["vehicle_metadata_source"] = event.entities["vehicle_metadata_source"]
        if event.entities.get("vehicle_year"):
            parameters["vehicle_year"] = event.entities["vehicle_year"]

        return ParameterBuildResult(
            parameters=parameters,
            confidence=Confidence.from_score(_transport_confidence(event, distance)),
            assumptions=assumptions,
        )


class GoodsServicesParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        metadata = GOODS_SERVICES_TAXONOMY.get(event.activity_type, {})
        product_class = _entity_text(event.entities.get("product_class"))
        pathway = metadata.get("pathways", {}).get(product_class)
        parameters = {"product_class": product_class} if product_class else {}
        issues = _delivery_context_issues(event)
        if event.entities.get("delivery_context"):
            parameters["delivery_context"] = "delivery_app"

        if pathway is None:
            parameters.update(_preserved_quantity_parameters(event.quantities))
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.25),
                issues=[
                    *issues,
                    Issue(
                        code="goods_services.product.unsupported_pathway",
                        message=(
                            "Detected a purchased food or drink component, but it does not "
                            "map to a maintained product-and-unit factor pathway."
                        ),
                        severity="warning",
                    ),
                ],
                can_estimate=False,
            )

        required_dimension = str(pathway["required_dimension"])
        quantity = _first_quantity(event.quantities, required_dimension)
        assumptions: list[Assumption] = []
        if (
            quantity is None
            and required_dimension == "number"
            and pathway.get("infer_singular_item")
            and _first_quantity(event.quantities, "money") is None
        ):
            parameters.update({"number": 1.0, "number_unit": "item"})
            assumptions.append(
                singular_item_count_assumption(
                    event.activity_type,
                    product_class.replace("_", " "),
                )
            )
            confidence = Confidence.from_score(0.62)
        elif quantity is None and _first_quantity(event.quantities, "money") is not None:
            money = _first_quantity(event.quantities, "money")
            parameters.update(
                {
                    "money": _round_quantity(money.value),
                    "money_unit": money.unit,
                }
            )
            confidence = Confidence.from_score(0.90)
            issues.append(
                Issue(
                    code="goods_services.money_factor_unavailable",
                    message=(
                        "This product pathway needs a compatible money-based factor; "
                        "purchase price is not converted into item count."
                    ),
                    severity="warning",
                )
            )
        elif quantity is None:
            parameters.update(_preserved_quantity_parameters(event.quantities))
            missing_code = (
                "goods_services.money_factor_unavailable"
                if _first_quantity(event.quantities, "money") is not None
                else "goods_services.missing_quantity"
            )
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.25),
                issues=[
                    *issues,
                    Issue(
                        code=missing_code,
                        message=(
                            "This product pathway needs an explicit compatible quantity; "
                            "purchase price is not converted into item count."
                        ),
                        severity="warning",
                    ),
                ],
                can_estimate=False,
            )
        else:
            parameters.update(
                {
                    required_dimension: _round_quantity(quantity.value),
                    f"{required_dimension}_unit": str(pathway["calculation_unit"]),
                }
            )
            confidence = Confidence.from_score(0.93)

        if required_dimension in parameters:
            parameters["calculation_boundary"] = str(pathway["boundary_note"])
        if pathway.get("fallback_factor_key"):
            parameters["fallback_factor_key"] = str(pathway["fallback_factor_key"])
        return ParameterBuildResult(
            parameters=parameters,
            confidence=confidence,
            assumptions=assumptions,
            issues=issues,
        )


class WasteParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        metadata = WASTE_TAXONOMY.get(event.activity_type, {})
        disposal_method = _entity_text(event.entities.get("disposal_method"))
        material_class = _entity_text(event.entities.get("material_class"))
        parameters = {
            "disposal_method": disposal_method or "unknown",
            "material_class": material_class or "unknown",
        }
        material_description = event.entities.get("material_description")
        if material_description:
            parameters["material_description"] = material_description

        if disposal_method in {"", "unknown"}:
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.20),
                issues=[
                    Issue(
                        code="waste.disposal_method.ambiguous",
                        message=(
                            "Detected discarded materials, but the disposal method "
                            "was not stated clearly enough to estimate."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        weight = _first_quantity(event.quantities, "weight")
        if weight is None:
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.25),
                issues=[
                    Issue(
                        code="waste.missing_weight",
                        message=(
                            "A disposal method was detected, but an explicit waste mass "
                            "is required; no mass is assumed for bags or containers."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        pathway = metadata.get("pathways", {}).get(material_class)
        if pathway is None and material_class in {"", "unknown", "mixed"}:
            parameters.update({"weight": _round_quantity(weight.value), "weight_unit": "kg"})
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.25),
                issues=[
                    Issue(
                        code="waste.material.unsupported_or_mixed",
                        message=(
                            "The stated material mix is not represented by one maintained "
                            "factor pathway, so no material-specific estimate was made."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        parameters.update(
            {
                "weight": _round_quantity(weight.value),
                "weight_unit": "kg",
            }
        )
        if pathway is not None and pathway.get("fallback_factor_key"):
            parameters["fallback_factor_key"] = str(pathway["fallback_factor_key"])
        return ParameterBuildResult(
            parameters=parameters,
            confidence=Confidence.from_score(0.93),
        )


def _first_quantity(quantities: list[Quantity], dimension: str) -> Quantity | None:
    return next((quantity for quantity in quantities if quantity.dimension == dimension), None)


def _round_quantity(value: float) -> float:
    return round(float(value), 3)


def _transport_confidence(event: CarbonEvent, distance: Quantity) -> float:
    score = min(
        event.confidence.score,
        distance.confidence,
        float(event.entities.get("vehicle_confidence") or 0.60),
    )
    if event.entities.get("vehicle_typo_corrected"):
        score -= 0.03
    if any(issue.code == "vehicle.fuel_type.contradiction" for issue in event.issues):
        score = min(score, 0.50)
    return score


def _distance_confidence(event: CarbonEvent, distance: Quantity) -> float:
    return min(event.confidence.score, distance.confidence)


def _is_compact_k_distance(quantity: Quantity) -> bool:
    return bool(quantity.surface and re.match(r"^\d+(?:\.\d+)?\s*k$", quantity.surface, re.I))


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _add_declared_transport_traits(parameters: dict, event: CarbonEvent, metadata: dict) -> None:
    for field in metadata.get("factor_trait_fields", ()):
        value = _entity_text(event.entities.get(str(field)))
        if value:
            parameters[str(field)] = value


def _add_geospatial_transport_parameters(parameters: dict, event: CarbonEvent) -> None:
    for field in (
        "origin",
        "destination",
        "origin_place_id",
        "destination_place_id",
        "origin_place_name",
        "destination_place_name",
        "origin_place_type",
        "destination_place_type",
        "origin_region",
        "destination_region",
        "origin_matched_alias",
        "destination_matched_alias",
        "origin_match_type",
        "destination_match_type",
        "distance_source",
        "route_exact",
        "route_source_version",
        "route_path_place_ids",
        "route_path_place_names",
        "origin_route_node_id",
        "destination_route_node_id",
        "route_path_node_ids",
        "route_path_edge_ids",
        "snap_source",
        "origin_snap_source",
        "destination_snap_source",
    ):
        value = event.entities.get(field)
        if value is not None:
            parameters[field] = value
    for field in (
        "origin_confidence",
        "destination_confidence",
        "distance_confidence",
        "snap_confidence",
        "origin_snap_distance_m",
        "destination_snap_distance_m",
        "origin_snap_confidence",
        "destination_snap_confidence",
    ):
        value = event.entities.get(field)
        if isinstance(value, (int, float)):
            parameters[field] = round(float(value), 3)


def _energy_region_parameters(event: CarbonEvent) -> dict:
    region = _entity_text(event.entities.get("region"))
    if not region:
        return {}
    parameters = {"region": region.upper()}
    for field in (
        "region_name",
        "factor_region",
        "fallback_region",
        "region_source",
        "region_source_version",
    ):
        value = event.entities.get(field)
        if value is not None:
            parameters[field] = value
    confidence = event.entities.get("region_confidence")
    if isinstance(confidence, (int, float)):
        parameters["region_confidence"] = round(float(confidence), 3)
    return parameters


def _add_flight_factor_defaults(
    parameters: dict,
    event: CarbonEvent,
    distance: Quantity,
    assumptions: list[Assumption],
) -> None:
    route_type = _entity_text(event.entities.get("route_type"))
    passenger_class = _entity_text(event.entities.get("passenger_class"))
    parameters["route_type"] = route_type or "domestic"
    parameters["passenger_class"] = passenger_class or "average"
    parameters["rf_effect"] = "included"
    parameters["distance_band"] = (
        "short_haul" if float(distance.value) < 3700 else "long_haul"
    )
    assumptions.append(
        flight_default_factor_assumption(
            assumed_route=not bool(route_type),
            assumed_passenger_class=not bool(passenger_class),
        )
    )


def _preserved_quantity_parameters(quantities: list[Quantity]) -> dict:
    parameters = {}
    for dimension in ("number", "weight", "money"):
        quantity = _first_quantity(quantities, dimension)
        if quantity is not None:
            parameters[dimension] = _round_quantity(quantity.value)
            parameters[f"{dimension}_unit"] = quantity.unit
    return parameters


def _delivery_context_issues(event: CarbonEvent) -> list[Issue]:
    if not event.entities.get("delivery_context"):
        return []
    return [
        Issue(
            code="goods_services.delivery_transport.not_included",
            message=(
                "Delivery-app context was preserved, but no delivery travel emissions "
                "are included because no distance or transport method was supplied."
            ),
            severity="info",
        )
    ]
