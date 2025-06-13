import pytest
from langchain.schema import BaseRetriever

from app.vectorstores.pgvector_store import PgVectorStore


class _DummyStore:
    def __init__(self, *args, **kwargs):
        self.kwargs = None

    def as_retriever(self, *, search_kwargs=None, **kwargs):
        self.kwargs = search_kwargs
        return _DummyRetriever()


class _DummyRetriever(BaseRetriever):
    def _get_relevant_documents(self, query: str, *, run_manager=None):
        return []

    async def _aget_relevant_documents(self, query: str, *, run_manager=None):
        return []


def test_filter_conversion(monkeypatch):
    monkeypatch.setattr('app.vectorstores.pgvector_store.PGVector', _DummyStore)
    store = PgVectorStore('JACSKE_Program')
    r = store.as_retriever({'where_filter': {
        'path': ['use4RAG'],
        'operator': 'Equal',
        'valueBoolean': True,
    }})
    assert isinstance(r, BaseRetriever)
    assert store._store.kwargs['filter'] == {'use4RAG': {'$eq': True}}
