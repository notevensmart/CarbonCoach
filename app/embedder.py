from __future__ import annotations

from typing import Dict, List

from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.services.climatiq_api import get_activity_lookup


model = None
vector_store = None


def init_vector_store() -> None:
    global vector_store
    lookup = get_activity_lookup()
    docs = [
        Document(
            page_content=description,
            metadata={"activity_id": activity_id},
        )
        for description, activity_id in lookup.items()
    ]
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=_get_model(),
        persist_directory="./chroma_store",
    )


def retrieve_best_activities(labels: List[str]) -> Dict[str, dict]:
    if vector_store is None:
        raise RuntimeError("Vector store not initialized. Did you call init_vector_store()?")

    embeddings = _get_model().embed_documents(labels)
    matched_dict = {}

    for label, vector in zip(labels, embeddings):
        result = vector_store.similarity_search_by_vector(vector, k=1)
        if result:
            matched_dict[label] = {
                "activity_name": result[0].page_content,
                "activity_id": result[0].metadata["activity_id"],
            }
        else:
            matched_dict[label] = None

    return matched_dict


def _get_model():
    global model
    if model is None:
        model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return model
