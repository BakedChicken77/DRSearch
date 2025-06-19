# file: app/chain/retriever.py

from __future__ import annotations

from langchain_core.retrievers import BaseRetriever

from app.chain.exceptions import ConfigurationError
from app.core import chain_config
from app.index_config import INDEX_CONFIG
from app.vectorstores.factory import VectorStoreFactory


class RetrieverFactory:
    """Factory for langchain retrievers backed by configured vector store."""

    @staticmethod
    def build(index_name: str) -> BaseRetriever:
        """Return a configured retriever for index_name.

        Raises ConfigurationError if index_name not in INDEX_CONFIG.
        """
        cfg = INDEX_CONFIG.get(index_name)
        if cfg is None:
            raise ConfigurationError(
                f"Index '{index_name}' not defined in INDEX_CONFIG"
            )

        store = VectorStoreFactory.create(index_name)

        filter_rag_only = {
            "operator": "Equal",
            "path": ["use4RAG"],
            "valueBoolean": True,
        }

        return store.as_retriever(
            search_kwargs={
                "k": chain_config._NUMBER_OF_DOCS_RETRIEVED,
                "where_filter": filter_rag_only,
            }
        )
