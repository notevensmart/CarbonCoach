from __future__ import annotations


ENERGY_TAXONOMY = {
    "electricity_use": {
        "category": "energy",
        "keywords": ("electricity", "power", "kwh", "kilowatt hour"),
        "required_quantity_dimensions": ("energy",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "energy",
        "fallback_factor_key": "energy.au_electricity_kwh",
        "default_assumptions": ("region.default_au_electricity",),
    },
    "space_heater_use": {
        "category": "energy",
        "keywords": ("heater", "space heater", "heating"),
        "required_quantity_dimensions": ("energy",),
        "supporting_quantity_dimensions": ("duration", "power"),
        "derivation_rules": (
            "power + duration -> energy",
            "duration + default_power -> energy",
        ),
        "parameter_builder": "energy",
        "fallback_factor_key": "energy.au_electricity_kwh",
        "default_assumptions": (
            "space_heater.default_power",
            "region.default_au_electricity",
        ),
    },
}

TRANSPORT_TAXONOMY = {
    "car_ride": {
        "category": "transport",
        "keywords": ("drive", "drove", "driving", "ride", "trip", "commute", "car"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": ("duration", "number"),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": "transport.car_distance",
        "default_assumptions": ("vehicle.generic_car.default_petrol_medium",),
    },
    "bus_ride": {
        "category": "transport",
        "keywords": ("bus",),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": "transport.bus_distance",
        "default_assumptions": (),
    },
    "train_ride": {
        "category": "transport",
        "keywords": ("train", "rail"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": "transport.train_distance",
        "default_assumptions": (),
    },
    "flight": {
        "category": "transport",
        "keywords": ("flight", "flew", "plane"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": "transport.flight_distance",
        "default_assumptions": (),
    },
    "rideshare": {
        "category": "transport",
        "keywords": ("uber", "rideshare", "taxi"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": ("duration",),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": "transport.car_distance",
        "default_assumptions": ("vehicle.generic_car.default_petrol_medium",),
    },
    "bicycle_ride": {
        "category": "transport",
        "keywords": ("bike", "bicycle", "cycling"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": None,
        "default_assumptions": (),
    },
    "walking": {
        "category": "transport",
        "keywords": ("walk", "walking"),
        "required_quantity_dimensions": ("distance",),
        "supporting_quantity_dimensions": (),
        "derivation_rules": (),
        "parameter_builder": "transport",
        "fallback_factor_key": None,
        "default_assumptions": (),
    },
}

ACTIVITY_TAXONOMY = {
    **ENERGY_TAXONOMY,
    **TRANSPORT_TAXONOMY,
}
