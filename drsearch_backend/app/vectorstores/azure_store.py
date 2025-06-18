from __future__ import annotations

from typing import Any

from langchain_community.vectorstores.azuresearch import (
    AzureSearch as LangchainAzureSearch,
)
from langchain_core.retrievers import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config

from . import VectorStore


class AzureVectorStore(VectorStore):
    """Vector store backed by Azure Cognitive Search."""

    def __init__(self, index_name: str) -> None:
        self._store = LangchainAzureSearch(
            azure_search_endpoint=chain_config._AZURE_SEARCH_ENDPOINT,
            azure_search_key=chain_config._AZURE_SEARCH_KEY,
            index_name=index_name,
            embedding_function=EmbeddingFactory.get(),
        )

    def as_retriever(self, search_kwargs: dict[str, Any]) -> BaseRetriever:
        return self._store.as_retriever(search_kwargs=search_kwargs)
