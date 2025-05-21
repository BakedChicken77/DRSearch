from __future__ import annotations

from typing import Iterable, List

import weaviate
from langchain_community.vectorstores import Weaviate as LCWeaviate
from langchain.schema import Document
from langchain.schema.retriever import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core.chain_config import _WEAVIATE_API_KEY, _WEAVIATE_URL
from .base import VectorStore


class WeaviateVectorStore(VectorStore):
    """Vector store implementation backed by Weaviate."""

    def __init__(self, index_name: str, text_key: str, attributes: list[str]):
        self.index_name = index_name
        self.client = weaviate.Client(
            url=_WEAVIATE_URL,
            auth_client_secret=weaviate.AuthApiKey(api_key=_WEAVIATE_API_KEY),
        )
        self._store = LCWeaviate(
            client=self.client,
            index_name=index_name,
            text_key=text_key,
            embedding=EmbeddingFactory.get(),
            by_text=False,
            attributes=attributes,
        )

    def store_vector(self, docs: Iterable[Document]) -> None:
        self._store.add_documents(list(docs))

    def query_similar(self, query: str, k: int, where: dict | None = None) -> List[Document]:
        return self._store.similarity_search(query, k=k, where=where)

    def delete_vector(self, doc_id: str) -> None:
        self.client.batch.delete_objects(
            class_name=self.index_name,
            where={"path": ["id"], "operator": "Equal", "valueString": doc_id},
        )

    def update_vector(self, doc_id: str, doc: Document) -> None:
        self.delete_vector(doc_id)
        self.store_vector([doc])

    def as_retriever(self, **kwargs) -> BaseRetriever:
        return self._store.as_retriever(**kwargs)
