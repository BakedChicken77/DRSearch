from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from langchain.schema import Document
from langchain.schema.retriever import BaseRetriever


class VectorStore(ABC):
    """Abstract interface for vector database implementations."""

    @abstractmethod
    def store_vector(self, docs: Iterable[Document]) -> None:
        """Persist documents to the vector database."""
        raise NotImplementedError

    @abstractmethod
    def query_similar(self, query: str, k: int, where: dict | None = None) -> List[Document]:
        """Return documents similar to *query*."""
        raise NotImplementedError

    @abstractmethod
    def delete_vector(self, doc_id: str) -> None:
        """Delete document with *doc_id* from the vector database."""
        raise NotImplementedError

    @abstractmethod
    def update_vector(self, doc_id: str, doc: Document) -> None:
        """Replace an existing document by *doc_id* with *doc*."""
        raise NotImplementedError

    @abstractmethod
    def as_retriever(self, **kwargs) -> BaseRetriever:
        """Return a langchain retriever for this store."""
        raise NotImplementedError
