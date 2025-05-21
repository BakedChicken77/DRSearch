import os
import sys
from types import ModuleType
from unittest import mock

import pytest


# Prepare dummy modules for vector stores
class DummyVector:
    def __init__(self):
        self.deleted = []

    def delete(self, ids=None):
        self.deleted.append(ids)


def create_dummy_weaviate_modules():
    weaviate_mod = ModuleType("weaviate")
    weaviate_mod.Client = mock.MagicMock(return_value="client")
    weaviate_mod.AuthApiKey = mock.MagicMock(return_value="auth")
    lc_mod = ModuleType("langchain_community.vectorstores")
    lc_mod.Weaviate = mock.MagicMock(return_value=DummyVector())
    return {"weaviate": weaviate_mod, "langchain_community.vectorstores": lc_mod}


def create_dummy_pgvector_modules():
    lc_mod = ModuleType("langchain_community.vectorstores")
    lc_mod.PGVector = mock.MagicMock(return_value=DummyVector())
    return {"langchain_community.vectorstores": lc_mod}


@pytest.mark.parametrize("backend", ["weaviate", "pgvector"])
def test_from_config_creates_backend(backend):
    modules = {}
    if backend == "weaviate":
        modules = create_dummy_weaviate_modules()
    else:
        modules = create_dummy_pgvector_modules()
    with mock.patch.dict(sys.modules, modules, clear=False):
        env = {
            "VECTOR_DB_BACKEND": backend,
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_API_KEY": "key",
            "PGVECTOR_CONNECTION": "postgresql://user:pass@localhost/db",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            from docextract.vector_store import from_config, WeaviateVectorStore, PgVectorStore

            store = from_config("idx", "text", embedding="emb")
            if backend == "weaviate":
                assert isinstance(store, WeaviateVectorStore)
            else:
                assert isinstance(store, PgVectorStore)


def test_wrapper_delete_calls_underlying():
    dummy = DummyVector()
    modules = {
        "langchain_community.vectorstores": mock.MagicMock(PGVector=mock.MagicMock(return_value=dummy))
    }
    with mock.patch.dict(sys.modules, modules, clear=False):
        with mock.patch.dict(os.environ, {"VECTOR_DB_BACKEND": "pgvector", "PGVECTOR_CONNECTION": "x", "WEAVIATE_URL": "", "WEAVIATE_API_KEY": ""}):
            from docextract.vector_store import from_config

            store = from_config("idx", "text", embedding="emb")
            store.delete(["1", "2"])
            assert dummy.deleted == [["1", "2"]]
