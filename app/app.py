import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.embedder import init_vector_store
from app.pipeline import pipeline
from app.pipeline_v2.pipeline import pipeline_v2
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
react_build_dir = Path(__file__).resolve().parent / "frontend" / "build"
react_index_path = react_build_dir / "index.html"


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

if (react_build_dir / "static").exists():
    app.mount(
        "/static",
        StaticFiles(directory=react_build_dir / "static"),
        name="react-static",
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


@app.post("/api/estimate-v2")
async def estimate_emissions_v2(request: Request):
    readiness_error = await _readiness_error_async()
    if readiness_error:
        return readiness_error

    try:
        data = await request.json()
        if not isinstance(data, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Request body must be a JSON object"},
            )
        journal = data.get("journal", "")
        if not isinstance(journal, str):
            return JSONResponse(
                status_code=400,
                content={"error": "'journal' must be a string"},
            )
        if not journal.strip():
            return JSONResponse(status_code=400, content={"error": "Missing 'journal' field"})

        return pipeline_v2(journal)

    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Request body must be valid JSON"})
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


@app.get("/", response_class=HTMLResponse)
async def serve_react_root():
    return _serve_react_app()


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react_routes(full_path: str):
    if full_path.startswith("api/") or full_path in {"healthz", "process"}:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    static_asset = _react_build_asset(full_path)
    if static_asset:
        return FileResponse(static_asset)
    return _serve_react_app()


def _serve_react_app():
    if react_index_path.exists():
        return HTMLResponse(react_index_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        status_code=503,
        content="""
        <html>
            <head><title>CarbonCoach</title></head>
            <body>
                <h1>CarbonCoach frontend build not found</h1>
                <p>Run <code>npm run build</code> in <code>app/frontend</code> or rebuild the Docker image.</p>
            </body>
        </html>
        """,
    )


def _react_build_asset(full_path: str) -> Path | None:
    candidate = (react_build_dir / full_path).resolve()
    try:
        candidate.relative_to(react_build_dir.resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None
