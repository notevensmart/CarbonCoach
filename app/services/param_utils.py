category_param_templates = {
    "transport": {
        "required": ["distance", "distance_unit"],
        "default": {"distance": 10, "distance_unit": "km"}
    },
    "waste": {
        "required": ["weight", "weight_unit"],
        "default": {"weight": 1, "weight_unit": "kg"}
    },
    "energy": {
        "required": ["energy", "energy_unit"],
        "default": {"energy": 5, "energy_unit": "kWh"}
    },
    
    "goods_services": {
        "required": ["number"],
        "default": {"number" : 1}
    }
}
def get_default_params(category: str) -> dict:
    template = category_param_templates.get(category)
    if template:
        return template["default"]
    return {"number" : 1}              
