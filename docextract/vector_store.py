from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, List


class BaseVectorStore(ABC):
    """Abstract base class for vector database backends."""

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """Delete vectors by ids."""

    @property
    @abstractmethod
    def inner(self) -> Any:
        """Return underlying vector store used by LangChain."""


class WeaviateVectorStore(BaseVectorStore):
    """Vector store backed by Weaviate."""

    def __init__(self, client: Any, index_name: str, text_key: str, embedding: Any, attributes: List[str] | None = None) -> None:
        from langchain_community.vectorstores import Weaviate

        self._store = Weaviate(
            client=client,
            index_name=index_name,
            text_key=text_key,
            embedding=embedding,
            by_text=False,
            attributes=attributes,
        )

    def delete(self, ids: List[str]) -> None:  # pragma: no cover - simple forwarder
        self._store.delete(ids=ids)

    @property
    def inner(self) -> Any:  # pragma: no cover - trivial
        return self._store


class PgVectorStore(BaseVectorStore):
    """Vector store backed by PostgreSQL with pgvector."""

    def __init__(self, connection_string: str, collection_name: str, embedding: Any, text_key: str) -> None:
        from langchain_community.vectorstores import PGVector

        self._store = PGVector(
            connection_string=connection_string,
            collection_name=collection_name,
            embedding_function=embedding,
            text_key=text_key,
        )

    def delete(self, ids: List[str]) -> None:  # pragma: no cover - simple forwarder
        self._store.delete(ids=ids)

    @property
    def inner(self) -> Any:  # pragma: no cover - trivial
        return self._store


def from_config(index_name: str, text_key: str, embedding: Any, attributes: List[str] | None = None) -> BaseVectorStore:
    """Instantiate a vector store backend based on environment configuration."""
    backend = os.getenv("VECTOR_DB_BACKEND", "weaviate").lower()

    if backend == "pgvector":
        connection = os.getenv("PGVECTOR_CONNECTION")
        if not connection:
            raise ValueError("PGVECTOR_CONNECTION environment variable not set")
        return PgVectorStore(
            connection_string=connection,
            collection_name=index_name,
            embedding=embedding,
            text_key=text_key,
        )

    # Default to Weaviate
    import weaviate

    client = weaviate.Client(
        url=os.getenv("WEAVIATE_URL"),
        auth_client_secret=weaviate.AuthApiKey(os.getenv("WEAVIATE_API_KEY")),
    )
    return WeaviateVectorStore(
        client=client,
        index_name=index_name,
        text_key=text_key,
        embedding=embedding,
        attributes=attributes,
    )
