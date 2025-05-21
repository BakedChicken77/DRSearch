from __future__ import annotations

import os

from .weaviate_store import WeaviateVectorStore
from .pgvector_store import PgVectorStore


def get_vector_store(index_name: str, *, text_key: str, attributes: list[str]):
    """Return a VectorStore instance according to ``VECTOR_BACKEND`` env-var."""
    backend = os.getenv("VECTOR_BACKEND", "weaviate").lower()
    if backend == "weaviate":
        return WeaviateVectorStore(index_name, text_key, attributes)
    if backend == "pgvector":
        return PgVectorStore(index_name)
    raise ValueError(f"Unsupported VECTOR_BACKEND '{backend}'")
