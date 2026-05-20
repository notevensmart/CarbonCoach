from app.embedder import init_vector_store
from app.pipeline import pipeline
from app.services import climatiq_api


if __name__ == "__main__":
    climatiq_api.load_activity_lookup()
    init_vector_store()
    result = pipeline("I took a 5 km bus ride")
    print(result)
