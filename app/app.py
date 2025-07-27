from fastapi import FastAPI,Form,Request
from app.pipeline import pipeline
from app.services.gcs_utils import download_files
from fastapi.responses import HTMLResponse
from app.embedder import init_vector_store
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


data_dir = "/tmp/data"
file_list = [
    ("carboncoach-data", "Climatiq_Energy_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Goods_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Transport_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Waste_ActivityIDs.csv"),
]
async def lifespan(app: FastAPI):
    # This runs on startup
    print("🚀 Lifespan startup triggered")

    os.makedirs(data_dir, exist_ok=True)

    # Download files synchronously
    download_files(file_list, data_dir)

    # Load activity lookup synchronously
    from app.services import climatiq_api
    lookup = climatiq_api.load_activity_lookup()
    climatiq_api.set_activity_lookup(lookup)
    init_vector_store()
    yield
app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def read_form():
    return """
    <html>
        <head>
            <title>CarbonCoach Journal</title>
        </head>
        <body>
            <h2>Enter Your Daily Journal</h2>
            <p>Describe your activities (e.g., commuting, shopping, meals). We will calculate your estimated CO2 emissions.</p>
            <form action="/process" method="post">
                <textarea name="journal_entry" rows="8" cols="80" placeholder="Today I drove 10 miles and ate beef..."></textarea><br>
                <input type="submit" value="Calculate Emissions">
            </form>
        </body>
    </html>
    """

@app.post("/process", response_class=HTMLResponse)
def process_entry(journal_entry: str = Form(...)):
    result = pipeline(journal_entry).replace("\n", "<br>")
    return f"""
    <html>
        <head>
            <title>CarbonCoach Results</title>
        </head>
        <body>
            <h2>Estimated Emissions</h2>
            <p>{result}</p>
            <a href="/">Back</a>
        </body>
    </html>
    """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can replace "*" with your Vercel frontend URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/api/estimate")
async def estimate_emissions(request: Request):
    try:
        data = await request.json()
        journal = data.get("journal", "")
        if not journal:
            return JSONResponse(status_code=400, content={"error": "Missing 'journal' field"})

        result_str = pipeline(journal)
        
        # You can parse out co2e and unit from the result string if needed
        # For now, return whole thing
        return {"co2e_text": result_str}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})