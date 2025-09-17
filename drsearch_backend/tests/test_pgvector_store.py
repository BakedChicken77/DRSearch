# test_pgvector_store.py (replace test_page_window_expands with this)
import pytest
from langchain.schema import BaseRetriever, Document

from app.vectorstores.pgvector_store import PgVectorStore
from app.core import chain_config


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
    monkeypatch.setattr("app.vectorstores.pgvector_store.PGVector", _DummyStore)
    store = PgVectorStore("JACSKE_Program")
    r = store.as_retriever(
        {
            "where_filter": {
                "path": ["use4RAG"],
                "operator": "Equal",
                "valueBoolean": True,
            }
        }
    )
    assert isinstance(r, BaseRetriever)
    assert store._store.kwargs["filter"] == {"use4RAG": {"$eq": True}}


def test_consolidates_and_expands(monkeypatch):
    """With PAGE_WINDOW > 0, results are consolidated per filename and expanded around hits."""

    # Use dummy vector store
    monkeypatch.setattr("app.vectorstores.pgvector_store.PGVector", _DummyStore)
    store = PgVectorStore("JACSKE_Program")

    # Base retriever returns a single semantic hit on page 5
    class _DocRetriever(BaseRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager=None):
            return [Document(page_content="orig", metadata={"filename": "f", "page_number": 5})]

        async def _aget_relevant_documents(self, query: str, *, run_manager=None):
            return [Document(page_content="orig", metadata={"filename": "f", "page_number": 5})]

    monkeypatch.setattr(
        store._store, "as_retriever", lambda *, search_kwargs=None, **k: _DocRetriever()
    )
    monkeypatch.setattr(chain_config, "_PAGE_WINDOW", 1)

    # New batched fetcher API: return pages 4..6 for filename 'f'
    def _fake_fetch_batched(self, filename_ranges, allowed):
        # filename_ranges == {"f": (4, 6)}
        pages = []
        for p in range(4, 7):
            pages.append(Document(page_content=str(p), metadata={"filename": "f", "page_number": p}))
        return {"f": pages}

    monkeypatch.setattr(PgVectorStore, "_fetch_page_ranges_batched", _fake_fetch_batched)

    retr = store.as_retriever({})
    docs = retr.get_relevant_documents("q")

    # Expect ONE consolidated doc covering 4-6
    assert len(docs) == 1
    d = docs[0]
    assert d.metadata["filename"] == "f"
    assert d.metadata["page_number"] == "4-6"
    # Content should be the merged page texts from the batched fetch
    assert "4" in d.page_content and "5" in d.page_content and "6" in d.page_content


def test_consolidates_with_zero_window(monkeypatch):
    """With PAGE_WINDOW == 0, consolidate across hit pages only (no neighbor expansion)."""

    monkeypatch.setattr("app.vectorstores.pgvector_store.PGVector", _DummyStore)
    store = PgVectorStore("JACSKE_Program")

    class _DocRetriever(BaseRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager=None):
            return [
                Document(page_content="p14", metadata={"filename": "report.pdf", "page_number": 14}),
                Document(page_content="p26", metadata={"filename": "report.pdf", "page_number": 26}),
                Document(page_content="p6",  metadata={"filename": "report2.pdf", "page_number": 6}),
            ]

    monkeypatch.setattr(store._store, "as_retriever", lambda *, **k: _DocRetriever())
    monkeypatch.setattr(chain_config, "_PAGE_WINDOW", 0)

    # Batched fetch should be called for report.pdf with range 14..26 and for report2.pdf with 6..6
    def _fake_fetch_batched(self, filename_ranges, allowed):
        out = {}
        for fname, (start, end) in filename_ranges.items():
            out[fname] = [
                Document(page_content=f"{fname}:{p}", metadata={"filename": fname, "page_number": p})
                for p in range(start, end + 1)
            ]
        return out

    monkeypatch.setattr(PgVectorStore, "_fetch_page_ranges_batched", _fake_fetch_batched)

    retr = store.as_retriever({})
    docs = retr.get_relevant_documents("q")

    # Expect two consolidated docs: report.pdf (14-26) and report2.pdf (6)
    d1, d2 = docs[0], docs[1]
    assert d1.metadata["filename"] == "report.pdf"
    assert d1.metadata["page_number"] == "14-26"
    assert "report.pdf:14" in d1.page_content and "report.pdf:26" in d1.page_content

    assert d2.metadata["filename"] == "report2.pdf"
    assert d2.metadata["page_number"] == 6 or d2.metadata["page_number"] == "6-6"
    assert "report2.pdf:6" in d2.page_content


def test_no_consolidation_when_negative_window(monkeypatch):
    """With PAGE_WINDOW == -1, no expansion or consolidation: original (stripped) docs returned."""

    monkeypatch.setattr("app.vectorstores.pgvector_store.PGVector", _DummyStore)
    store = PgVectorStore("JACSKE_Program")

    class _DocRetriever(BaseRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager=None):
            return [
                Document(page_content="p14", metadata={"filename": "report.pdf", "page_number": 14, "title": "T"}),
                Document(page_content="p26", metadata={"filename": "report.pdf", "page_number": 26, "title": "T"}),
                Document(page_content="p6",  metadata={"filename": "report2.pdf", "page_number": 6,  "title": "Y"}),
            ]

    monkeypatch.setattr(store._store, "as_retriever", lambda *, **k: _DocRetriever())
    monkeypatch.setattr(chain_config, "_PAGE_WINDOW", -1)

    # Batched fetcher should NOT be called; but stub anyway to catch accidental calls
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Should not call _fetch_page_ranges_batched when PAGE_WINDOW == -1")

    monkeypatch.setattr(PgVectorStore, "_fetch_page_ranges_batched", _fail_if_called)

    retr = store.as_retriever({})
    docs = retr.get_relevant_documents("q")

    # Expect three separate docs, same filenames/pages as input
    assert [d.metadata["page_number"] for d in docs] == [14, 26, 6]
    assert [d.metadata["filename"] for d in docs] == ["report.pdf", "report.pdf", "report2.pdf"]
