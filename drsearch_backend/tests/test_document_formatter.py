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


def test_formatter_falls_back_to_plain_text_when_html_too_large(monkeypatch):
    monkeypatch.setattr("app.core.chain_config.RAG_ON", False)
    mapping = PartNumberMapping(None)
    doc = Document(
        page_content="tiny",
        metadata={"filename": "doc.html", "text_as_html": "<p>tiny</p>"},
    )
    prefix = "<doc id='0' source='doc.html'>"
    suffix = "</doc>"
    limit = len(prefix) + len(suffix) + len(doc.page_content)
    formatter = DocumentFormatter(mapping, max_chars=limit)

    out = formatter([doc])

    assert "<p>tiny</p>" not in out
    assert ">tiny</doc>" in out


def test_formatter_truncates_when_plain_text_still_exceeds_limit(monkeypatch):
    monkeypatch.setattr("app.core.chain_config.RAG_ON", False)
    mapping = PartNumberMapping(None)
    doc = Document(page_content="abcdefghij", metadata={"filename": "doc.txt"})
    prefix = "<doc id='0' source='doc.txt'>"
    suffix = "</doc>"
    limit = len(prefix) + len(suffix) + 3
    formatter = DocumentFormatter(mapping, max_chars=limit)

    out = formatter([doc])

    assert out.endswith("abc</doc>")
    assert len(out) == limit
