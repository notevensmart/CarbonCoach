import os

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.embedder import init_vector_store
from app.pipeline import pipeline
from app.services.gcs_utils import download_files


data_dir = "/tmp/data"
file_list = [
    ("carboncoach-data", "Climatiq_Energy_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Goods_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Transport_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Waste_ActivityIDs.csv"),
]


async def lifespan(app: FastAPI):
    print("Lifespan startup triggered")
    os.makedirs(data_dir, exist_ok=True)
    download_files(file_list, data_dir)

    from app.services import climatiq_api

    print("Loading activity lookup...")
    climatiq_api.load_activity_lookup(data_dir)
    print("Initializing vector store...")
    init_vector_store()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/process")
def process_entry(journal_entry: str = Form(...)):
    return JSONResponse(content=pipeline(journal_entry))


@app.post("/api/estimate")
async def estimate_emissions(request: Request):
    try:
        data = await request.json()
        journal = data.get("journal", "")
        if not journal:
            return JSONResponse(status_code=400, content={"error": "Missing 'journal' field"})

        return pipeline(journal)

    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
