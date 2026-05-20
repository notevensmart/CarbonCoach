from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from dotenv import load_dotenv
from langchain_core.documents import Document
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
        _load_env_file("key.env")
        hf_token = os.getenv("HF_TOKEN")
        model = _load_embedding_model(hf_token)
    return model


def _load_embedding_model(hf_token: str | None):
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    if hf_token:
        try:
            return HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"token": hf_token},
            )
        except Exception as exc:
            print(f"HF_TOKEN embedding load failed, retrying without token: {exc}")

    return HuggingFaceEmbeddings(model_name=model_name)


def _load_env_file(filename: str) -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / filename
        if candidate.exists():
            load_dotenv(dotenv_path=candidate)
            return
