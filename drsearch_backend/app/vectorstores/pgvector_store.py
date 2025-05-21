from __future__ import annotations

from typing import Any

from langchain_community.vectorstores.pgvector import PGVector
from langchain.schema.retriever import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config

from . import VectorStore


class PgVectorStore(VectorStore):
    """Vector store backed by PostgreSQL with pgvector."""

    def __init__(self, index_name: str) -> None:
        self._store = PGVector(
            connection_string=chain_config._PGVECTOR_URL,
            embedding_function=EmbeddingFactory.get(),
            collection_name=index_name,
        )

    def as_retriever(self, search_kwargs: dict[str, Any]) -> BaseRetriever:
        return self._store.as_retriever(search_kwargs=search_kwargs)
