
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from app.services.climatiq_api import get_activity_lookup
from langchain.schema import Document
from typing import List,Dict
sentences = ["This is an example sentence", "Each sentence is converted"]

model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
lookup = get_activity_lookup()
## create database in chroma
docs = [
    Document(
        page_content=desc,
        metadata={"activity_id": activity_id}
    )
    for desc, activity_id in lookup.items()
]
vector_store = Chroma.from_documents(
    documents=docs,
    embedding=model,
    persist_directory="./chroma_store"
)
'''Function that creates vector embeddings for labels and loops through 
each label and matches its embedding with one in the chroma databse based on simialrity. Outputs a '''
def retrieve_best_activities(labels: List[str])->Dict[str,dict]:
    embeddings = model.embed_documents(labels)

    # Step 2: Search for each embedded label vector
    matched_dict = {}

    for label, vector in zip(labels, embeddings):
        result = vector_store.similarity_search_by_vector(vector, k=1)
        if result:
            matched_dict[label] = {
                "activity_name": result[0].page_content,
                "activity_id": result[0].metadata["activity_id"]
            }
            
        else:
            matched_dict[label] = None  # fallback if no match

    return matched_dict