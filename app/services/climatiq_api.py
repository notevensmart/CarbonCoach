import os
import pandas as pd
import requests
from dotenv import load_dotenv
def load_activity_lookup(data_dir="data"):
    """
    Scans all activity_ids_*.csv files in the given directory,
    and builds a dict mapping `name` → `activity_id`.
    """
    activity_lookup = {}

    for filename in os.listdir(data_dir):
        if filename.startswith("Climatiq") and filename.endswith(".csv"):
            filepath = os.path.join(data_dir, filename)
            df = pd.read_csv(filepath)

            for _, row in df.iterrows():
                name = str(row["name"]).strip().lower()        # Normalized key
                activity_id = str(row["activity_id"]).strip()  # API value
                activity_lookup[name] = activity_id

    return activity_lookup

# Load once globally when the module is imported
activity_lookup = load_activity_lookup()



def get_activity_id(description: str):
    """
    Direct string match from classifier output to the lookup table.
    """
    return activity_lookup.get(description.strip().lower())

load_dotenv("climatiq.env")

CLIMATIQ_BASE_URL = "https://api.climatiq.io"
CLIMATIQ_API_KEY = os.getenv("CLIMATIQ_API_KEY")
def get_emissions(activity_id: str, parameters: dict):
    headers = {
        "Authorization": f"Bearer {CLIMATIQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "emission_factor": {"activity_id": activity_id,
        "data_version": "^22", 
    },
    "parameters": parameters
    
    }

    response = requests.post(f"{CLIMATIQ_BASE_URL}/estimate", headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        co2 = data.get("co2e", None)
        unit = data.get("co2e_unit", None)
        print(f"🌱 Emission estimate: {co2} {unit}")
        return co2, unit
    else:
        print("❌ Climatiq API error:", response.status_code, response.text)
        return None, None