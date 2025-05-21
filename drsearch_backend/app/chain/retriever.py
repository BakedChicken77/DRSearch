# file: app/chain/retriever.py

from __future__ import annotations

import weaviate
from langchain.schema.retriever import BaseRetriever
from langchain_community.vectorstores import Weaviate as WeaviateStore

from app.chain.exceptions import ConfigurationError
from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config
from app.index_config import INDEX_CONFIG


class RetrieverFactory:
    """Factory for langchain retrievers backed by Weaviate."""

    @staticmethod
    def build(index_name: str) -> BaseRetriever:
        """Return a configured retriever for index_name.

        Raises ConfigurationError if index_name not in INDEX_CONFIG.
        """
        cfg = INDEX_CONFIG.get(index_name)
        if cfg is None:
            raise ConfigurationError(f"Index '{index_name}' not defined in INDEX_CONFIG")

        client = weaviate.Client(
            url=chain_config._WEAVIATE_URL,
            auth_client_secret=weaviate.AuthApiKey(api_key=chain_config._WEAVIATE_API_KEY),
        )
        store = WeaviateStore(
            client=client,
            index_name=index_name,
            text_key=cfg["index_key"],
            embedding=EmbeddingFactory.get(),
            by_text=False,
            attributes=cfg["attributes"],
        )

        filter_rag_only = {
            "operator": "Equal",
            "path": ["use4RAG"],
            "valueBoolean": True,
        }
        return store.as_retriever(
            search_kwargs={"k": chain_config._NUMBER_OF_DOCS_RETRIEVED, "where_filter": filter_rag_only}
        )
