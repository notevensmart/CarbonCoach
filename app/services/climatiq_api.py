import os
import pandas as pd
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