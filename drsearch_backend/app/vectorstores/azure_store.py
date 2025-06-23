from __future__ import annotations

from typing import Any
import logging

logger = logging.getLogger(__name__)

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
        base = self._store.as_retriever(search_kwargs=search_kwargs)

        class _LoggedRetriever(BaseRetriever):
            def _get_relevant_documents(self, query: str, *, run_manager=None):
                docs = base.get_relevant_documents(query)
                logger.info(
                    "retriever returned %d documents",
                    len(docs),
                    extra={"query": query, "doc_count": len(docs)},
                )
                return docs

            async def _aget_relevant_documents(self, query: str, *, run_manager=None):
                docs = await base.ainvoke(query)
                logger.info(
                    "retriever returned %d documents",
                    len(docs),
                    extra={"query": query, "doc_count": len(docs)},
                )
                return docs

        return _LoggedRetriever()
