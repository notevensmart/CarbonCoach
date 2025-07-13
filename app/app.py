from fastapi import FastAPI
from app.main import pipeline
from utils.gcs_utils import download_files
from contextlib import asynccontextmanager
import os
app = FastAPI()


data_dir = "/tmp/data"
file_list = [
    ("carboncoach-data", "Climatiq_Energy_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Goods_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Transport_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Waste_ActivityIDs.csv"),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs on startup
    os.makedirs(data_dir, exist_ok=True)
    download_files(file_list, data_dir)
    yield
app = FastAPI(lifespan=lifespan)

@app.post("/process")
def process_entry(journal_entry: str):
    result = pipeline(journal_entry)
    return {"result": result}
