import pytest  # type: ignore
from langchain.schema import Document  # type: ignore

from app.vectorstores.pgvector_store import PgVectorStore


class _FakeBaseRetriever:
    def __init__(self, docs):
        self._docs = docs

    def get_relevant_documents(self, query, callbacks=None):  # noqa: D401
        return list(self._docs)

    async def aget_relevant_documents(self, query, callbacks=None):  # noqa: D401
        return list(self._docs)


class _FakePGVector:
    """Stub for PGVector that just returns a dummy retriever."""

    def __init__(self, *_, **__):
        self._docs = [
            Document(page_content="foo", metadata={"filename": "a.pdf", "drop": "x"})
        ]

    def as_retriever(self, search_kwargs=None):  # noqa: D401
        return _FakeBaseRetriever(self._docs)


@pytest.fixture(autouse=True)
def _patch_pg(monkeypatch):
    monkeypatch.setattr(
        "app.vectorstores.pgvector_store.PGVector", _FakePGVector, raising=False
    )
    yield


def test_convert_filter_variants():
    f = PgVectorStore._convert_filter
    assert f(None) is None
    assert f({}) is None

    inp = {"operator": "Equal", "path": ["filename"], "valueString": "abc"}
    assert f(inp) == {"filename": {"$eq": "abc"}}

    inp_bool = {"operator": "Equal", "path": ["flag"], "valueBoolean": True}
    assert f(inp_bool) == {"flag": {"$eq": True}}

    # Unknown operator should fall back to original dict
    untouched = {"operator": "Gt", "path": ["x"], "valueNumber": 5}
    assert f(untouched) is untouched


def test_as_retriever_strips_metadata():
    store = PgVectorStore("TEST_INDEX")
    retriever = store.as_retriever({})

    docs = retriever._get_relevant_documents("query")  # type: ignore[attr-defined]
    assert docs[0].metadata == {"filename": "a.pdf"}  # only allowed attribute kept