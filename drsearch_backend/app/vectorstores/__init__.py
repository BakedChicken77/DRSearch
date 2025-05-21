from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain.schema.retriever import BaseRetriever


class VectorStore(ABC):
    """Abstract interface for vector store backends."""

    @abstractmethod
    def as_retriever(self, search_kwargs: dict[str, Any]) -> BaseRetriever:
        """Return a LangChain retriever for this store."""
        raise NotImplementedError


__all__ = ["VectorStore"]
