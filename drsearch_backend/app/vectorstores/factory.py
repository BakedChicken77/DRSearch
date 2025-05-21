from __future__ import annotations

from . import VectorStore
from .weaviate_store import WeaviateVectorStore
from .pgvector_store import PgVectorStore
from app.core import chain_config


class VectorStoreFactory:
    """Instantiate vector store backend based on configuration."""

    @staticmethod
    def create(index_name: str) -> VectorStore:
        if chain_config._VECTOR_BACKEND == "pgvector":
            return PgVectorStore(index_name)
        return WeaviateVectorStore(index_name)
