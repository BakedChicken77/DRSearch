import os
import json
import types
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

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
    # Auth (turned OFF for most tests – can be re-enabled where needed)
    "AUTH_ENABLED": "False",
    "CORS_ORIGINS": "http://localhost",
    "AZURE_AD_TENANT_ID": "11111111-1111-1111-1111-111111111111",
    "AZURE_AD_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
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


class _FakeWeavStore:
    def __init__(self, *a, **k):
        ...

    def as_retriever(self, *a, **k):
        return "retriever-ok"


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
    yield


# --------------------------------------------------------------------------- #
#  FastAPI TestClient (uses *real* router, but with auth disabled)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def fastapi_client():
    from app import create_app

    return TestClient(create_app())
