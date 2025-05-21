from __future__ import annotations

from typing import Iterable, List

from langchain_community.vectorstores.pgvector import PGVector
from langchain.schema import Document
from langchain.schema.retriever import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core.chain_config import _PGVECTOR_CONNECTION
from .base import VectorStore


class PgVectorStore(VectorStore):
    """Vector store implementation backed by PostgreSQL with pgvector."""

    def __init__(self, index_name: str):
        self.index_name = index_name
        self._store = PGVector(
            connection_string=_PGVECTOR_CONNECTION,
            embedding_function=EmbeddingFactory.get(),
            collection_name=index_name,
        )

    def store_vector(self, docs: Iterable[Document]) -> None:
        self._store.add_documents(list(docs))

    def query_similar(self, query: str, k: int, where: dict | None = None) -> List[Document]:
        return self._store.similarity_search(query, k=k, filter=where)

    def delete_vector(self, doc_id: str) -> None:
        self._store.delete(doc_id)

    def update_vector(self, doc_id: str, doc: Document) -> None:
        self.delete_vector(doc_id)
        self.store_vector([doc])

    def as_retriever(self, **kwargs) -> BaseRetriever:
        return self._store.as_retriever(**kwargs)
