from app.chains.classify_chain import classify_activities
from app.services.llm_matcher import batch_match_activities
from app.services.climatiq_api import get_emissions , get_activity_id, extract_unit_info
from app.services.param_utils import get_default_params ,generate_params
from app.embedder import retrieve_best_activities

def pipeline(journal_entry):
  
    ##step 1 convert journal entry into acivity labels
    activities = classify_activities(journal_entry)
    results = []
    total_emissions = 0.0

    labels = [label for label, category in activities]

    
    matched_dict = retrieve_best_activities(labels)

    for (label, category) in activities:
        match = matched_dict.get(label)
       
        print(f"\n🔍 Processing label: {label} | Category: {category}")
        if not match:
            print(f"❌ No match found for label '{label}'")
            results.append(f" No match found for '{label}'")
            continue

        print(f"✅ Found match: {match}")
        activity_id = match.get("activity_id")
      
        if not activity_id:
            print(f"❌ No activity ID in match for '{label}' → {match}")
            results.append(f" No activity ID found for '{match['activity_name']}'")
            continue
        unit_type,unit = extract_unit_info(activity_id)
        if not unit_type:
            print(f"❌ No unit types found for activity {activity_id}")
            results.append(f" {label} → No valid unit types found")
            continue
        params = generate_params(unit_type)    
        print(f"→ Calling API: {label} → activity_id: {activity_id}, params: {params} , unit_type: {unit_type}")

        co2, unit = get_emissions(activity_id, params)
        if co2:
            results.append(f" {label} ({category}) → {round(co2,3)} {unit} CO2e")
            total_emissions += co2
        else:
            results.append(f" {label} ({category}) → Emission lookup failed")


    summary = f"\n🧾 Total Emissions: {round(total_emissions,3)} kg CO2e"
    return "\n".join(results + [summary])




