from app.chains.classify_chain import classify_activities
from app.services.llm_matcher import match_activity
from app.services.climatiq_api import get_emissions
from app.services.param_utils import get_default_params

journal_entry = "I took a 10 km bus ride to work, ate three vegetarian meals and took a shower."

# Step 1: Classify
activities = classify_activities(journal_entry)
print(f"🧠 LLM-classified labels: {activities}")

total_emissions = 0.0
emission_unit = "kg"  # default to kg CO2e

# Step 2: Loop through each label → match → estimate
for label, category in activities:
    activity_id = match_activity(label)

    if activity_id:
        params = get_default_params(category)
        co2, unit = get_emissions(activity_id, params)

        if co2 is not None:
            print(f"🌱 Emissions for '{label}' → {co2} {unit} CO2e")
            total_emissions += co2
            emission_unit = unit  # update unit in case it varies
        else:
            print(f"⚠️ Could not calculate emissions for: {label}")
    else:
        print(f"⚠️ No match found for: {label}")

# Step 3: Print total
print(f"\n🧾 Total CO2 emissions: {round(total_emissions, 3)} {emission_unit}")
