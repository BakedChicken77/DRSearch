from langchain.schema import Document
import os

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from app.chain.formatter import DocumentFormatter
from app.chain.mapping import PartNumberMapping


def test_formatter_deduplicates_and_adds_mapping(monkeypatch):
    rows = [("abc.pdf", "\\\\share\\abc.pdf")]

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def execute(self, _q):
            pass

        def fetchall(self):
            return rows

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def cursor(self):
            return DummyCursor()

    monkeypatch.setattr("app.chain.mapping.psycopg2.connect", lambda *_a, **_k: DummyConn())

    mapping = PartNumberMapping("tbl")
    formatter = DocumentFormatter(mapping)

    docs = [
        Document(page_content="same-text", metadata={"filename": "abc.pdf"}),
        Document(page_content="same-text", metadata={"filename": "abc.pdf"}),
    ]

    out = formatter(docs)

    assert out.count("<doc") == 1
    assert formatter._mapping["abc.pdf"] == "\\\\share\\abc.pdf"


def test_formatter_prefers_html(monkeypatch):
    """HTML documents should be preferred when content is duplicated."""
    monkeypatch.setattr("app.core.chain_config.RAG_ON", False)
    formatter = DocumentFormatter(PartNumberMapping(None))
    docs = [
        Document(page_content="same", metadata={"filename": "doc.html"}),
        Document(page_content="same", metadata={"filename": "doc.pdf"}),
    ]

    out = formatter(docs)

    assert out.startswith("<doc id='0' source='doc.html'>")
