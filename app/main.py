from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .services.carbon_pipeline import CarbonEstimator


class EstimateRequest(BaseModel):
    journal: str = Field(..., min_length=1)


app = FastAPI(title="CarbonCoach API")
estimator = CarbonEstimator()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/estimate")
def estimate(request: EstimateRequest) -> dict:
    result = estimator.estimate(request.journal)
    if result["errors"] and not result["activities"]:
        raise HTTPException(status_code=400, detail=result["errors"][0])
    return result


frontend_build = Path(__file__).resolve().parent / "frontend" / "build"
if frontend_build.exists():
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="frontend")
