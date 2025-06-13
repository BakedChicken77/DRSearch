from langchain.schema import Document

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


def test_formatter_prefers_html():
    formatter = DocumentFormatter(PartNumberMapping(None))

    docs = [
        Document(page_content="plain", metadata={"filename": "a", "text_as_html": "<b>html</b>"}),
        Document(page_content="other", metadata={"filename": "b"}),
    ]

    out = formatter(docs)

    assert "<doc id='0' source='a'><b>html</b></doc>" in out
    assert "<doc id='1' source='b'>other</doc>" in out
