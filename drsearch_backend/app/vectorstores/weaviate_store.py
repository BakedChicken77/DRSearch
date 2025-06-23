from __future__ import annotations

from typing import Any
import logging

logger = logging.getLogger(__name__)

import weaviate
from langchain_community.vectorstores import Weaviate as LangchainWeaviate
from langchain_core.retrievers import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config
from app.index_config import INDEX_CONFIG

from . import VectorStore


class WeaviateVectorStore(VectorStore):
    """Vector store backed by Weaviate."""

    def __init__(self, index_name: str) -> None:
        cfg = INDEX_CONFIG[index_name]
        client = weaviate.Client(
            url=chain_config._WEAVIATE_URL,
            auth_client_secret=weaviate.AuthApiKey(
                api_key=chain_config._WEAVIATE_API_KEY
            ),
        )
        self._store = LangchainWeaviate(
            client=client,
            index_name=index_name,
            text_key=cfg["index_key"],
            embedding=EmbeddingFactory.get(),
            by_text=False,
            attributes=cfg["attributes"],
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
