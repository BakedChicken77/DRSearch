from __future__ import annotations

from typing import Any

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
        return self._store.as_retriever(search_kwargs=search_kwargs)
