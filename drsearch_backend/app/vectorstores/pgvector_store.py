from __future__ import annotations

from typing import Any, Iterable

from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.retrievers import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config
from app.index_config import INDEX_CONFIG

from . import VectorStore


class PgVectorStore(VectorStore):
    """Vector store backed by PostgreSQL with pgvector."""

    def __init__(self, index_name: str) -> None:
        cfg = INDEX_CONFIG[index_name]
        self._attributes: Iterable[str] = cfg["attributes"]
        self._store = PGVector(
            connection_string=chain_config._PGVECTOR_URL,
            embedding_function=EmbeddingFactory.get(),
            collection_name=index_name,
        )

    @staticmethod
    def _convert_filter(where: dict[str, Any] | None) -> dict[str, Any] | None:
        """Translate Weaviate-style filters to PGVector format."""
        if not where:
            return None

        op = where.get("operator")
        path = where.get("path")
        if op == "Equal" and isinstance(path, list) and path:
            field = path[0]
            for key in (
                "valueBoolean",
                "valueText",
                "valueString",
                "valueInt",
                "valueNumber",
            ):
                if key in where:
                    return {field: {"$eq": where[key]}}
        return where

    def as_retriever(self, search_kwargs: dict[str, Any]) -> BaseRetriever:
        """Return retriever while normalising filters and metadata output."""

        kw = dict(search_kwargs)
        if "where_filter" in kw:
            kw["filter"] = self._convert_filter(kw.pop("where_filter"))

        base = self._store.as_retriever(search_kwargs=kw)

        allowed = set(self._attributes)

        def _strip(docs):
            for doc in docs:
                doc.metadata = {k: v for k, v in doc.metadata.items() if k in allowed}
            return docs

        class _FilteredRetriever(BaseRetriever):
            def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
                docs = base.get_relevant_documents(query, callbacks=run_manager)
                return _strip(docs)

            async def _aget_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
                docs = await base.aget_relevant_documents(query, callbacks=run_manager)
                return _strip(docs)

        return _FilteredRetriever()
