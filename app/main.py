from app.pipeline import pipeline
from app.embedder import init_vector_store
from app.services import climatiq_api


    # Load activity lookup synchronously
   
lookup = climatiq_api.load_activity_lookup()
print("🔧 Setting activity lookup...")
climatiq_api.set_activity_lookup(lookup)
prompt = "I took a bus"
init_vector_store()
result = pipeline(prompt)
print(result)

