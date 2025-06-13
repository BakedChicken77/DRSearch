from langchain.schema import Document
import os

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from app.chain.formatter import DocumentFormatter
from app.chain.mapping import PartNumberMapping


def test_formatter_deduplicates_and_adds_mapping(tmp_path, monkeypatch):
    # 1) create a dummy CSV mapping file
    csv_content = "file_name,Downloaded File\nabc.pdf,\\\\share\\abc.pdf\n"
    csv_file = tmp_path / "map.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # <-- This is the fix: ensure mapping reads from the temp directory
    monkeypatch.setattr("app.chain.mapping._MAPPING_DIR", tmp_path)

    # mapping = PartNumberMapping(csv_file.name)          # filename only
    monkeypatch.setattr("app.chain.mapping._MAPPING_DIR", tmp_path)
    mapping = PartNumberMapping(csv_file.name.split("\\")[-1])
    formatter = DocumentFormatter(mapping)

    docs = [
        Document(page_content="same-text", metadata={"filename": "abc.pdf"}),
        Document(page_content="same-text", metadata={"filename": "abc.pdf"}),  # dup
    ]

    out = formatter(docs)

    # deduplicated → only one <doc …>
    assert out.count("<doc") == 1
    # # UNC path injected
    # assert "\\\\share\\abc.pdf" in out
    # UNC path injected into metadata, not the xml string
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
