🌱 CarbonCoach

CarbonCoach is an AI-powered sustainability tool that estimates daily carbon emissions from free-text journal entries.
The goal is to help individuals and organizations understand and reduce their carbon footprint through transparent and accurate CO₂e estimates.

🚀 Project Status

Current version: v0.5 (Deterministic pipeline)

Next milestone: v0.7 (Agentic workflow with class-based architecture, logging, and CI/CD)

⚙️ How It Works (Current Pipeline)

The current backend uses a deterministic function pipeline.
Each journal entry is processed step-by-step in a fixed order:
## Workflow
Journal[User Journal Entry] --> Segmentation[Segmentation into Activities (Claude)] <br>
    Segmentation --> Embedding[Embed each Activity into Vector] <br>
    Embedding --> Compare[Compare with Stored Activity Embeddings] <br>
    Compare --> Match[Select Activity ID with Highest Cosine Similarity] <br>
    Match --> API[Call Climatiq API with Activity IDs] <br>
    API --> Extract[Extract Emissions from JSON Response] <br>
    Extract --> Return[Return Results to User] <br>

🔹 Steps

search_activity_ids(text)
Retrieves candidate emission activities (via Climatiq API or embeddings index).
Output: candidates = [{"id": ..., "label": ...}, ...]

pick_activity_id(text, candidates)
Chooses the most relevant activity for the user’s description.
Output: activity_id = "transport-public_bus_km"

extract_quantity(text)
Extracts numeric values and units from text (e.g., "11 km").
Output: {"value": 11, "unit": "km"}

estimate_emissions(activity_id, value, unit)
Calls the Climatiq API to compute carbon emissions.
Output: {"co2e": 2.34, "co2e_unit": "kg"}

🧩 Example Usage
journal = "I took the bus to work for 11 km"

candidates = search_activity_ids(journal)
activity_id = pick_activity_id(journal, candidates)
quantity = extract_quantity(journal)
estimate = estimate_emissions(activity_id, quantity["value"], quantity["unit"]) <br>

print(estimate)
➝ {"co2e": 2.34, "co2e_unit": "kg"}
Important project files:
app/pipeline.py
app/embedder.py
app/services/climatiq_api.py
app/chains/classify_chain.py

