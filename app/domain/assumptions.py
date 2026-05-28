from __future__ import annotations

from app.domain.models import Assumption


DEFAULT_REGION = "AU"
DEFAULT_ELECTRICITY_REGION = "AU"
SPACE_HEATER_DEFAULT_POWER_KW = 1.5


def space_heater_default_power_assumption() -> Assumption:
    return Assumption(
        code="space_heater.default_power",
        message="Assumed heater power of 1.5 kW because wattage was not provided.",
        source="default",
        confidence_impact=-0.25,
    )


def default_au_electricity_region_assumption() -> Assumption:
    return Assumption(
        code="region.default_au_electricity",
        message="Assumed Australia electricity grid because no region was provided.",
        source="default",
        confidence_impact=-0.05,
    )


def distance_compact_k_context_assumption(surface: str) -> Assumption:
    return Assumption(
        code="distance.compact_k_context_km",
        message=f'Interpreted "{surface}" as kilometres based on transport context.',
        source="inference",
        confidence_impact=-0.23,
    )


def flight_default_factor_assumption(
    *,
    assumed_route: bool,
    assumed_passenger_class: bool,
) -> Assumption:
    assumed_details = []
    if assumed_route:
        assumed_details.append("domestic route")
    if assumed_passenger_class:
        assumed_details.append("average passenger class")
    assumed_details.append("radiative forcing effects included")
    return Assumption(
        code="flight.default_factor_parameters",
        message=(
            "Assumed "
            + ", ".join(assumed_details)
            + " because complete flight factor details were not provided."
        ),
        source="default",
        confidence_impact=-0.25,
    )


def vehicle_model_default_assumption(code: str, display_name: str) -> Assumption:
    messages = {
        "vehicle.toyota_camry.default_petrol_medium": (
            "Mapped Toyota Camry to a medium petrol passenger car because model year "
            "and fuel type were not provided."
        ),
        "vehicle.tesla_model_3.default_electric": (
            "Mapped Tesla Model 3 to a medium electric passenger car because model "
            "year was not provided."
        ),
        "vehicle.tesla.default_electric": (
            "Mapped Tesla to an electric passenger car because Tesla vehicles are "
            "normally electric and no model was provided."
        ),
    }
    return Assumption(
        code=code,
        message=messages.get(code, f"Mapped {display_name} to local vehicle defaults."),
        source="default",
        confidence_impact=-0.15,
    )


def generic_car_default_assumption() -> Assumption:
    return Assumption(
        code="vehicle.generic_car.default_petrol_medium",
        message="Assumed a medium petrol passenger car because vehicle details were not provided.",
        source="default",
        confidence_impact=-0.30,
    )


def generic_car_size_default_assumption() -> Assumption:
    return Assumption(
        code="vehicle.generic_car.default_medium",
        message="Assumed a medium passenger car because vehicle size was not provided.",
        source="default",
        confidence_impact=-0.10,
    )


def named_vehicle_default_assumption(
    vehicle_description: str,
    vehicle_size: str | None = None,
) -> Assumption:
    if vehicle_size:
        return Assumption(
            code="vehicle.named.default_petrol",
            message=(
                f"Assumed petrol for {vehicle_description} because its fuel type "
                "was not provided or verified."
            ),
            source="default",
            confidence_impact=-0.20,
        )
    return Assumption(
        code="vehicle.named.default_petrol_medium",
        message=(
            f"Recognized the supplied vehicle name {vehicle_description}, but no verified "
            "class or fuel mapping is available; supplied medium petrol passenger-car "
            "parameters for the Climatiq estimate."
        ),
        source="fallback",
        confidence_impact=-0.30,
    )


def named_vehicle_size_default_assumption(vehicle_description: str) -> Assumption:
    return Assumption(
        code="vehicle.named.default_medium",
        message=(
            f"Assumed a medium passenger car for {vehicle_description} because its body "
            "class was not provided or verified."
        ),
        source="default",
        confidence_impact=-0.10,
    )


def explicit_fuel_override_assumption(
    vehicle_name: str,
    default_fuel: str,
    explicit_fuel: str,
) -> Assumption:
    return Assumption(
        code="vehicle.fuel_type.user_override",
        message=(
            f"Used the explicit {explicit_fuel} fuel type from the journal for "
            f"{vehicle_name} instead of the local {default_fuel} default."
        ),
        source="user",
        confidence_impact=0.0,
    )


def singular_item_count_assumption(activity_type: str, product_label: str) -> Assumption:
    return Assumption(
        code=f"{activity_type}.inferred_single_serving",
        message=f"Assumed one {product_label} serving because a singular item was described.",
        source="inference",
        confidence_impact=-0.25,
    )


def generic_waste_fallback_assumption(material_class: str, disposal_method: str) -> Assumption:
    material_label = material_class.replace("_", " ")
    method_label = disposal_method.replace("_", " ")
    return Assumption(
        code=f"waste.{disposal_method}.generic_fallback",
        message=(
            f"Used a general {method_label} waste factor because no compatible "
            f"{material_label}-specific {method_label} factor was found."
        ),
        source="fallback",
        confidence_impact=-0.25,
    )
