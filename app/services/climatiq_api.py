import os
import pandas as pd
import requests
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import csv

def load_activity_lookup():
    """
    Scans all activity_ids_*.csv files in the given directory,
    and builds a dict mapping `name` → `activity_id`.
    """
    lookup = {}
    for filename in os.listdir("/tmp/data"):
        if filename.endswith(".csv"):
            with open(os.path.join("/tmp/data", filename), encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("name", "").strip().lower()
                    activity_id = row.get("activity_id", "").strip()
                    if name and activity_id:
                        lookup[name] = activity_id
    return lookup

# Load once globally when the module is imported


def set_activity_lookup(lookup):
    global _activity_lookup
    _activity_lookup = lookup

def get_activity_lookup():
    """
    Always loads or returns the lookup dict.
    In production you can cache it.
    """
    return _activity_lookup


def get_activity_id(description: str):
    lookup = get_activity_lookup()
    if not lookup:
        raise RuntimeError("activity_lookup is not loaded yet.")
    return lookup.get(description.strip().lower())


load_dotenv(dotenv_path="climatiq.env")
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

def extract_unit_info(activity_id: str) -> tuple[str, str]:
    url = f"https://www.climatiq.io/data/activity/{activity_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            print("[ERROR] <script id='__NEXT_DATA__'> not found.")
            return "unknown", "unknown"

        data = json.loads(script_tag.string)
        page_props = data.get("props", {}).get("pageProps", {})

        # Try 'factor' first
        factor_data = page_props.get("factor") or (
            page_props.get("factors", [{}])[0] if page_props.get("factors") else {}
        )

        unit_type = factor_data.get("unit_type", "unknown").lower()
        unit = factor_data.get("unit", "unknown").lower()

        print(f"[DEBUG] unit_type: {unit_type}, unit: {unit}")
        return unit_type, unit

    except Exception as e:
        print(f"[Scrape Error] {e}")
        return "unknown", "unknown"

def search_activity_ids(query: str, limit: int = 3):
    payload = {
        "query": query,
        "results_per_page": limit,
        "data_version": "^21"
    }
    HEADERS = {
    "Authorization": f"Bearer {CLIMATIQ_API_KEY}",
    "Content-Type": "application/json"
    }
    url = CLIMATIQ_BASE_URL + "/data/v1/search"
    try:
        response = requests.get(url,headers=HEADERS, params=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        for hit in data.get("results", []):
            results.append({
                "activity_id": hit.get("activity_id"),
                "name": hit.get("name"),
                "category": hit.get("category"),
                "unit_type": hit.get("unit_type"),
                "unit": hit.get("unit")
            })

        return results

    except Exception as e:
        print(f"[ERROR] Climatiq Search failed for query='{query}': {e}")
        return []