import os
import json
import types
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from langchain.schema import BaseRetriever

# --------------------------------------------------------------------------- #
#  Global environment & dummy values
# --------------------------------------------------------------------------- #
_DUMMY_ENV: Dict[str, str] = {
    # Weaviate / Azure / OpenAI
    "WEAVIATE_URL": "http://weaviate:8080",
    "WEAVIATE_API_KEY": "dev-key",
    "AZURE_OPENAI_API_VERSION": "2024-05-15",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "dummy-model",
    "AZURE_OPENAI_ENDPOINT": "https://dummy-endpoint.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "dummy-key",
    "AZURE_SEARCH_ENDPOINT": "https://dummy-search.search.windows.net",
    "AZURE_SEARCH_KEY": "dummy-search-key",
    "VECTOR_BACKEND": "weaviate",
    "PGVECTOR_URL": "postgresql://user:pass@localhost/db",
    # RAG is enabled by default during tests
    "RAG_ON": "True",
    # Auth (turned OFF for most tests – can be re-enabled where needed)
    "AUTH_ENABLED": "False",
    "CORS_ORIGINS": "http://localhost",
    "AZURE_AD_TENANT_ID": "11111111-1111-1111-1111-111111111111",
    "AZURE_AD_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
    "LOG_OUTPUT_MODE": "local",
}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set every env-var required for app import without touching the host."""
    for k, v in _DUMMY_ENV.items():
        monkeypatch.setenv(k, v)
    yield


# --------------------------------------------------------------------------- #
#  Dummy LLM / Embeddings / Weaviate objects
# --------------------------------------------------------------------------- #
class _FakeLLM:  # mimics AzureChatOpenAI with sync `invoke`
    def __init__(self, *_, **__):
        ...

    def __call__(self, *_, **__):
        return "LLM-OK"

    def invoke(self, *_, **__):  # for compatibility with ChatEngine
        return "LLM-OK"


class _FakeEmbeddings:
    def __init__(self, model=None, chunk_size=None, api_version=None):
        pass

    def embed_query(self, query: str) -> list[float]:
        return [0.1] * 1536


class FakeQuery:
    def get(self, *a, **k):
        class Dummy:
            def with_near_vector(self, *a, **k):
                return self

            def with_additional(self, *a, **k):
                return self

            def with_where(self, *a, **k):
                return self

            def with_limit(self, *a, **k):
                return self

            def do(self):
                return {"data": {"Get": {}}}

        return Dummy()


class FakeClient:
    def __init__(self, *a, **k):
        self.query = FakeQuery()


class _DummyRetriever(BaseRetriever):
    """A simple synchronous retriever that always returns one predictable Document.
    This is sufficient for unit-tests that need a real ``BaseRetriever`` instance
    without hitting any external services.
    """

    def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
        from langchain.schema import Document

        return [
            Document(
                page_content=f"Dummy content for: {query}",
                metadata={"filename": "dummy.pdf"},
            )
        ]

    async def _aget_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
        # Just delegate to the sync implementation for test purposes.
        return self._get_relevant_documents(query, run_manager=run_manager)


class _FakeWeavStore:
    def __init__(self, *a, **k):
        ...

    def as_retriever(self, *a, **k):
        # Return a real BaseRetriever implementation rather than a string, so that
        # downstream components (e.g. MultiQueryRetriever) work as expected during
        # unit-tests.
        return _DummyRetriever()


class _FakePgVector:
    def __init__(self, *a, **k):
        ...

    def as_retriever(self, *a, **k):
        return _DummyRetriever()


class _FakeAzureStore:
    def __init__(self, *a, **k):
        ...

    def as_retriever(self, *a, **k):
        return _DummyRetriever()


@pytest.fixture(autouse=True)
def _patch_external(monkeypatch):
    # LLM & embeddings
    monkeypatch.setattr("app.chain.engine.AzureChatOpenAI", _FakeLLM, raising=False)
    monkeypatch.setattr(
        "app.chain.embeddings.AzureOpenAIEmbeddings", _FakeEmbeddings, raising=False
    )

    # Weaviate client and vector-store
    monkeypatch.setattr("weaviate.Client", FakeClient, raising=False)
    monkeypatch.setattr(
        "langchain_community.vectorstores.Weaviate", _FakeWeavStore, raising=False
    )
    monkeypatch.setattr(
        "langchain_community.vectorstores.pgvector.PGVector",
        _FakePgVector,
        raising=False,
    )
    monkeypatch.setattr(
        "app.vectorstores.pgvector_store.PGVector",
        _FakePgVector,
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_community.vectorstores.azuresearch.AzureSearch",
        _FakeAzureStore,
        raising=False,
    )
    monkeypatch.setattr(
        "app.vectorstores.azure_store.LangchainAzureSearch",
        _FakeAzureStore,
        raising=False,
    )
    yield


# --------------------------------------------------------------------------- #
#  FastAPI TestClient (uses *real* router, but with auth disabled)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def fastapi_client():
    from app import create_app

    return TestClient(create_app())
