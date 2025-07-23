from typing import List
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
def generate_params(unit_type: str) -> dict | None:
        match unit_type.lower():
            case "distance":
                return {"distance": 10, "distance_unit": "km"}
            case "energy":
                return {"energy": 5, "energy_unit": "kWh"}
            case "weight":
                return {"weight": 0.3, "weight_unit": "kg"}
            case "money":
                return {"money": 15, "money_unit": "usd"}
            case "area":
                return {"area": 0.5, "area_unit": "m2"}
            case "number":
                return {"number": 1}
            case "volume":
                return {"volume": 500, "volume_unit": "ml"}
        return None  # no match

def get_default_params(category: str) -> dict:
    template = category_param_templates.get(category)
    if template:
        return template["default"]
    return {"number" : 1}              
