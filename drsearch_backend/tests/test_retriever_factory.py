import types
import pytest
from langchain.schema import BaseRetriever

from app.chain.retriever import RetrieverFactory
from app.chain.exceptions import ConfigurationError


def test_retriever_factory_success(monkeypatch):
    EXPECTED = "retriever-ok"

    # _Fake objects are already patched in conftest
    r = RetrieverFactory.build("JACSKE_Program")
    assert isinstance(r, BaseRetriever)


def test_retriever_factory_bad_index(monkeypatch):
    with pytest.raises(ConfigurationError):
        RetrieverFactory.build("missing")


def test_retriever_factory_pgvector(monkeypatch):
    monkeypatch.setattr("app.core.chain_config._VECTOR_BACKEND", "pgvector")
    monkeypatch.setattr(
        "app.core.chain_config._PGVECTOR_URL",
        "postgresql://user:pass@localhost/db",
    )
    r = RetrieverFactory.build("JACSKE_Program")
    assert isinstance(r, BaseRetriever)


def test_retriever_factory_azure(monkeypatch):
    monkeypatch.setattr("app.core.chain_config._VECTOR_BACKEND", "azure")
    monkeypatch.setattr(
        "app.core.chain_config._AZURE_SEARCH_ENDPOINT",
        "https://dummy-search.search.windows.net",
    )
    monkeypatch.setattr(
        "app.core.chain_config._AZURE_SEARCH_KEY",
        "dummy-search-key",
    )
    r = RetrieverFactory.build("JACSKE_Program")
    assert isinstance(r, BaseRetriever)
