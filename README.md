README 
# 🌿 CarbonCoach
**An AI-powered web app that calculates your carbon emissions based on activities described in text.**

---

## 💡 Motivation

Current carbon emission calculators require users to fill out forms containing a large number of questions.  
However, they are limited because they simplify user activities into broad categories such as **energy**, **transport**, and **waste**, which reduces calculation accuracy.  

For example, travelling in a gasoline car versus an electric car under similar conditions yields substantially different carbon emissions.  
Therefore, the specificity of an activity is directly correlated to the accuracy of the estimate.  

However, requesting more specific input through traditional forms would only make the process more complex and time-consuming.  
To solve this, CarbonCoach integrates a language model (LLM) that analyzes user activities and matches them to emission activities in a large database based on similarity.  

This abstracts the complexity of manual input — allowing users to simply describe their daily actions in natural language, while the LLM intelligently interprets and maps them to precise emission factors.  
The result is both ease of use and higher accuracy in carbon estimation.  

CarbonCoach encourages **greater personal awareness**, **behavioural change**, and **collective progress** toward global sustainability goals.

---

## 🧩 System Architecture

CarbonCoach follows a linear pipeline that interprets user text, identifies specific activities, retrieves matching records through Retrieval-Augmented Generation (RAG), and computes emissions via an external API.

### **Pipeline Overview**
1. **User Input** → User submits a natural-language journal entry.  
2. **Segmentation** → LLM breaks text into discrete, carbon-relevant activity chunks.  
3. **Retrieval (RAG)** → Finds the closest matching emission factors from an embedded database.  
4. **Parameter Extraction** → Infers quantities and units (e.g., “11 km”, “2 kWh”).  
5. **Validation** → Confirms parameter compatibility using Climatiq metadata.  
6. **Emission Estimation** → Calls the Climatiq API to compute CO₂e emissions.  
7. **Response Generation** → Returns a structured JSON response with individual and total emissions.  
8. **Logging** → Records results for transparency and future memory tracking.

<img width="1024" height="1024" alt="CC system flow" src="https://github.com/user-attachments/assets/17130173-8f11-4341-9cf6-580e6013e180" />


## 🛠️ Tech Stack Summary

**CarbonCoach** is built with a modular, cloud-native AI architecture that combines language understanding, retrieval, and emissions computation in a unified FastAPI backend.

| Layer | Tools & Technologies | Purpose |
|-------|----------------------|----------|
| **Backend Framework** | **FastAPI**, **Uvicorn** | High-performance REST API for serving carbon estimation requests. |
| **Language & Runtime** | **Python 3.10+** | Core language for pipeline logic, orchestration, and model integration. |
| **LLM Orchestration** | **LangChain** | Manages multi-step reasoning, chaining of LLM calls, and RAG workflow execution. |
| **LLM Integration** | **Hugging Face Inference API** | Runs pre-trained transformer models to interpret user journal entries. |
| **Retrieval (RAG)** | **ChromaDB** + **Sentence Transformers (MiniLM-L6-v2)** | Retrieves the most relevant emission activities from embedded datasets. |
| **External Data Source** | **Climatiq API** | Provides verified emission factors and computes carbon emissions (CO₂e). |
| **Containerization & Deployment** | **Docker**, **Google Cloud Run** | Enables reproducible builds and serverless deployment with autoscaling. |
| **Storage & Logging** | **Google Cloud Storage (GCS)** | Stores processed data, logs, and emission lookups for traceability. |
| **Version Control & CI/CD** | **GitHub**, **GCP Cloud Build / GitHub Actions** | Manages continuous integration, testing, and automated deployments. |

### 💡 Summary

CarbonCoach integrates **LangChain’s LLM orchestration** with **retrieval-augmented generation (RAG)** and **verified emission APIs** to deliver precise, real-time carbon estimates.  
The system is packaged as a **Dockerized FastAPI service** and deployed on **Google Cloud Run**, ensuring reliability, scalability, and easy extensibility for future features like memory, user tracking, and agentic reasoning.

## 🚀 Example Final Output (Under the Hood)

CarbonCoach exposes a REST API that takes a natural-language journal entry and returns a structured carbon emission estimate.

### **Endpoint**
### **Request Example**
```bash
curl -X POST "http://localhost:8000/estimate" \
     -H "Content-Type: application/json" \
     -d '{"journal_entry": "I drove 10 km in a petrol car and had coffee at a café."}'

```
### **Response Example**
```bash
{
  "activities": [
    {
      "description": "Driving a petrol car",
      "activity_id": "passenger_vehicle-vehicle_type_car-fuel_source_petrol-engine_size_medium",
      "parameters": {
        "distance": 10,
        "unit": "km"
      },
      "emissions": {
        "co2e": 2.41,
        "unit": "kg"
      }
    },
    {
      "description": "Drinking coffee at a café",
      "activity_id": "food-beverage-coffee",
      "parameters": {
        "serving": 1,
        "unit": "cup"
      },
      "emissions": {
        "co2e": 0.28,
        "unit": "kg"
      }
    }
  ],
  "total_emissions": {
    "co2e": 2.69,
    "unit": "kg"
  },
  "explanation": "Based on your journal entry, the system matched two activities and retrieved their emission factors from Climatiq."
}
```
## 🌍 Potential Uses

CarbonCoach’s natural-language understanding and emission estimation capabilities make it applicable across several sustainability-focused use cases.

### **1. Personal Sustainability Tracking**
- Individuals can log daily activities (travel, meals, energy use) in plain text to monitor their personal carbon footprint.
- Encourages behaviour change by making sustainability tracking more intuitive and engaging.
- Can be integrated in apps that record a user's daily journal to give them carbon emission insights.

### **2. Corporate & Workplace Dashboards**
- Can be integrated into company sustainability dashboards to automate emission estimation for staff travel or operations.
- Supports businesses in ESG reporting and internal sustainability metrics.

### **3. Educational Tools**
- Useful for classroom demonstrations or university sustainability programs.
- Helps students explore how AI and environmental data can intersect to promote climate awareness.

## 🔮 Future Improvements

- Implement long-term memory and personalized user tracking.
- Improve parameter selection accuracy on ambiguous inputs. 
- Add conversational AI coaching (weekly sustainability summaries).  
- Expand database for regional emission factors.  
- Build interactive dashboard for live carbon insights.




