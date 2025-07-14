import uvicorn
from app.chains.classify_chain import classify_activities
from app.services.llm_matcher import batch_match_activities
from app.services.climatiq_api import get_emissions , get_activity_lookup
from app.services.param_utils import get_default_params

def pipeline(journal_entry):
    activities = classify_activities(journal_entry)
    results = []
    total_emissions = 0.0

    # Extract label strings
    labels = [label for label, category in activities]

    # Batch match all labels in a single call
    matched_dict = batch_match_activities(labels)

    for (label, category) in activities:
        matched_name = matched_dict.get(label)
        if matched_name:
            lookup = get_activity_lookup()
            activity_id = lookup.get(matched_name)
            if activity_id:
                params = get_default_params(category)
                co2, unit = get_emissions(activity_id, params)
                if co2:
                    results.append(f" {label} ({category}) → {round(co2,3)} {unit} CO2e")
                    total_emissions += co2
                else:
                    results.append(f" {label} ({category}) → Emission lookup failed")
            else:
                results.append(f" No activity ID found for '{matched_name}'")
        else:
            results.append(f" No match found for '{label}'")

    summary = f"\n🧾 Total Emissions: {round(total_emissions,3)} kg CO2e"
    return "\n".join(results + [summary])




