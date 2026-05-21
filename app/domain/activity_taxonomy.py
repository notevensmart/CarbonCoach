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

