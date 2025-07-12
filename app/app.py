from fastapi import FastAPI
from app.main import pipeline
from utils.gcs_utils import download_files
app = FastAPI()


data_dir = "/tmp/data"
file_list = [
    ("carboncoach-data", "Climatiq_Energy_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Goods_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Transport_ActivityIDs.csv"),
    ("carboncoach-data", "Climatiq_Waste_ActivityIDs.csv"),
]

download_files(file_list, data_dir)

@app.post("/process")
def process_entry(journal_entry: str):
    result = pipeline(journal_entry)
    return {"result": result}
