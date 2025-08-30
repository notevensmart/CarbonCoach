🌱 CarbonCoach

CarbonCoach is an AI-powered sustainability tool that estimates daily carbon emissions from free-text journal entries.
The goal is to help individuals understand and reduce their carbon footprint through transparent and accurate CO₂e estimates.

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


# Example Usage
journal = "I took the bus to work for 11 km" <br>
➝ {"co2e": 2.34, "co2e_unit": "kg"} <br>
Important project files: <br>
app/pipeline.py<br>
app/embedder.py <br>
app/services/climatiq_api.py<br>
app/chains/classify_chain.py<br>

