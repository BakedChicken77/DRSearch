import os
import types

import pytest  # type: ignore

from app.chain.embeddings import EmbeddingFactory


class _DummyAzureEmbed:
    """Lightweight stand-in for AzureOpenAIEmbeddings that records kwargs."""

    def __init__(self, *, model, chunk_size, api_version):  # noqa: D401
        self.model = model
        self.chunk_size = chunk_size
        self.api_version = api_version

    def embed_query(self, text):  # noqa: D401
        return [len(text)] * 3


@pytest.fixture(autouse=True)
def _reset_singleton():
    # Ensure EmbeddingFactory is fresh for every test to avoid cross-test bleed-over.
    EmbeddingFactory._instance = None  # type: ignore
    yield
    EmbeddingFactory._instance = None  # type: ignore


def test_fake_embedding_singleton(monkeypatch):
    """When LLM_SERVICE=fake the factory returns the inbuilt FakeEmbedder singleton."""
    monkeypatch.setenv("LLM_SERVICE", "fake")

    emb1 = EmbeddingFactory.get()
    emb2 = EmbeddingFactory.get()

    # Should be same object (singleton) and deterministic dimensions.
    assert emb1 is emb2
    vec = emb1.embed_query("hello")  # type: ignore[attr-defined]
    assert isinstance(vec, list) and len(vec) == 1536


def test_azure_embedding_path(monkeypatch):
    """Factory should instantiate AzureOpenAIEmbeddings when service != fake."""
    # Ensure service defaults to 'azure'.
    monkeypatch.delenv("LLM_SERVICE", raising=False)

    # Provide dummy env vars expected by embeddings path.
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDER", "my-model")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-05-15")

    # Patch underlying class so no network calls are performed.
    monkeypatch.setattr(
        "app.chain.embeddings.AzureOpenAIEmbeddings",
        _DummyAzureEmbed,
        raising=False,
    )

    emb = EmbeddingFactory.get()
    assert isinstance(emb, _DummyAzureEmbed)
    assert emb.model == "my-model"
    assert emb.chunk_size == 200
    assert emb.api_version == "2024-05-15"

    # Subsequent call should reuse instance even if env var toggled.
    monkeypatch.setenv("LLM_SERVICE", "fake")
    emb2 = EmbeddingFactory.get()
    assert emb2 is emb