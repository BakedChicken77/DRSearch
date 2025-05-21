# file: app/chain/retriever.py

from __future__ import annotations

from langchain.schema.retriever import BaseRetriever

from app.chain.exceptions import ConfigurationError
from app.core.chain_config import (
    _VECTOR_BACKEND,
    _NUMBER_OF_DOCS_RETRIEVED,
)
from app.index_config import INDEX_CONFIG
from app.vector_store import get_vector_store


class RetrieverFactory:
    """Factory for langchain retrievers backed by the configured vector store."""

    @staticmethod
    def build(index_name: str) -> BaseRetriever:
        """Return a configured retriever for index_name.

        Raises ConfigurationError if index_name not in INDEX_CONFIG.
        """
        cfg = INDEX_CONFIG.get(index_name)
        if cfg is None:
            raise ConfigurationError(f"Index '{index_name}' not defined in INDEX_CONFIG")

        store = get_vector_store(
            index_name,
            text_key=cfg["index_key"],
            attributes=cfg["attributes"],
        )

        filter_rag_only = {"use4RAG": True}
        search_kwargs = {"k": _NUMBER_OF_DOCS_RETRIEVED}
        if _VECTOR_BACKEND == "weaviate":
            search_kwargs["where_filter"] = {
                "operator": "Equal",
                "path": ["use4RAG"],
                "valueBoolean": True,
            }
        else:
            search_kwargs["filter"] = filter_rag_only

        return store.as_retriever(search_kwargs=search_kwargs)
