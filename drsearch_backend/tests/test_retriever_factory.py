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
