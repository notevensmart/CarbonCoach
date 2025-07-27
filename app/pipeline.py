from app.chains.classify_chain import classify_activities
from app.services.llm_matcher import batch_match_activities
from app.services.climatiq_api import get_emissions , get_activity_id, extract_unit_info 
from app.services.param_utils import get_default_params ,generate_params
from app.embedder import retrieve_best_activities

def pipeline(journal_entry):
    
    activities = classify_activities(journal_entry)
    total_emissions = 0.0
    details = []

    labels = [label for label, _ in activities]
    matched_dict = retrieve_best_activities(labels)

    for (label, category) in activities:
        match = matched_dict.get(label)
        detail = {
            "label": label,
            "category": category,
            "activity": None,
            "co2e": None,
            "unit": None,
            "status": "error",
            "error_message": ""
        }

        if not match:
            detail["error_message"] = f"No match found for '{label}'"
            details.append(detail)
            continue

        activity_id = match.get("activity_id")
        activity_name = match.get("activity_name")
        detail["activity"] = activity_name

        if not activity_id:
            detail["error_message"] = f"No activity ID found for '{activity_name}'"
            details.append(detail)
            continue

        unit_type, unit = extract_unit_info(activity_id)
        if not unit_type:
            detail["error_message"] = f"No valid unit types found for activity ID '{activity_id}'"
            details.append(detail)
            continue

        params = generate_params(unit_type)
        co2, unit = get_emissions(activity_id, params)

        if co2:
            detail["co2e"] = round(co2, 3)
            detail["unit"] = unit
            detail["status"] = "ok"
            total_emissions += co2
        else:
            detail["error_message"] = f"Emission lookup failed for activity '{activity_name}'"

        details.append(detail)

    summary_text = f"🧾 Total Emissions: {round(total_emissions, 3)} kg CO2e"

    return {
        "result": {
            "co2e": round(total_emissions, 3),
            "unit": "kg",
            "details": details,
            "summary": summary_text
        }
    }




