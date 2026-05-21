import asyncio
import os

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.embedder import init_vector_store
from app.pipeline import pipeline
from app.services import climatiq_api
from app.services.gcs_utils import download_files


data_dir = "/tmp/data"
preload_wait_seconds = int(os.getenv("PRELOAD_WAIT_SECONDS", "60"))
file_list = [
    ("carboncoach-data", "Climatiq_Energy_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Goods_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Transport_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Waste_ActivityIDs.csv"),
]

is_ready = False
preload_error = None
preload_started = False
preload_finished = False


async def lifespan(app: FastAPI):
    print("Lifespan startup triggered")
    preload_task = asyncio.create_task(asyncio.to_thread(_preload))
    yield
    if not preload_task.done():
        preload_task.cancel()


def _preload() -> None:
    global is_ready, preload_error, preload_started, preload_finished
    preload_started = True
    try:
        os.makedirs(data_dir, exist_ok=True)
        download_files(file_list, data_dir)
        print("Loading activity lookup...")
        climatiq_api.load_activity_lookup(data_dir)
        print("Initializing vector store...")
        init_vector_store()
        is_ready = True
        print("Preload finished")
    except Exception as exc:
        preload_error = str(exc)
        print(f"Preload failed: {exc}")
    finally:
        preload_finished = True


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {
        "status": "ok" if preload_error is None else "degraded",
        "ready": is_ready,
        "preload_started": preload_started,
        "preload_finished": preload_finished,
        "error": preload_error,
    }


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
async def process_entry(journal_entry: str = Form(...)):
    readiness_error = await _readiness_error_async()
    if readiness_error:
        return readiness_error
    return JSONResponse(content=pipeline(journal_entry))


@app.post("/api/estimate")
async def estimate_emissions(request: Request):
    readiness_error = await _readiness_error_async()
    if readiness_error:
        return readiness_error

    try:
        data = await request.json()
        journal = data.get("journal", "")
        if not journal:
            return JSONResponse(status_code=400, content={"error": "Missing 'journal' field"})

        return pipeline(journal)

    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


def _readiness_error():
    if preload_error:
        return JSONResponse(
            status_code=503,
            content={
                "error": "CarbonCoach failed to initialize.",
                "details": preload_error,
                "ready": is_ready,
                "preload_started": preload_started,
                "preload_finished": preload_finished,
            },
        )
    if not is_ready:
        return JSONResponse(
            status_code=503,
            content={
                "error": "CarbonCoach is still warming up. Please retry shortly.",
                "ready": is_ready,
                "preload_started": preload_started,
                "preload_finished": preload_finished,
            },
        )
    return None


async def _readiness_error_async(wait_seconds: int = preload_wait_seconds):
    for _ in range(wait_seconds * 10):
        if is_ready or preload_error:
            break
        await asyncio.sleep(0.1)
    return _readiness_error()
