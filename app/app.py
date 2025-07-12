from fastapi import FastAPI
from app.app import pipeline

app = FastAPI()

@app.post("/process")
def process_entry(journal_entry: str):
    result = pipeline(journal_entry)
    return {"result": result}
