import requests

API_KEY = "SCCDV0RCQD1AV7RN7SA3P8RDAR"  # Replace with your actual key
url = "https://api.climatiq.io/estimate"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "emission_factor": {
        "activity_id": "passenger_vehicle-vehicle_type_bus-fuel_source_na-engine_size_na-vehicle_age_na-vehicle_weight_na",
        "data_version": "^21",
    },
    "parameters": {
        "distance": 10,
        "distance_unit": "km"
    }
}

response = requests.post(url, headers=headers, json=payload)

if response.status_code == 200:
    data = response.json()
    print("✅ Success!")
    print("CO₂ emissions:", data["co2e"], data["co2e_unit"])
else:
    print("❌ Failed:", response.status_code)
    print(response.text)