import sys
import types
# Patch missing dependencies before importing DocumentProcessor
fake_pdf = types.ModuleType("unstructured.partition.pdf"); fake_pdf.partition_pdf=lambda *a, **k: []
fake_docx = types.ModuleType("unstructured.partition.docx"); fake_docx.partition_docx=lambda *a, **k: []
fake_xlsx = types.ModuleType("unstructured.partition.xlsx"); fake_xlsx.partition_xlsx=lambda *a, **k: []
fake_chunk = types.ModuleType("unstructured.chunking.title"); fake_chunk.chunk_by_title=lambda *a, **k: a[0] if a else []
sys.modules.setdefault("unstructured", types.ModuleType("unstructured"))
sys.modules.setdefault("unstructured.partition", types.ModuleType("unstructured.partition"))
sys.modules["unstructured.partition.pdf"] = fake_pdf
sys.modules["unstructured.partition.docx"] = fake_docx
sys.modules["unstructured.partition.xlsx"] = fake_xlsx
sys.modules["unstructured.chunking.title"] = fake_chunk
from pathlib import Path as _Path
sys.path.append(str(_Path(__file__).resolve().parents[2]))
from pathlib import Path
from types import SimpleNamespace

import pytest

from docextract.document_processor import DocumentProcessor


class FakeElement(SimpleNamespace):
    pass


def fake_partition(file=None, filename=None, **_kwargs):
    el = FakeElement()
    el.page_content = "text"
    el.category = "Body"
    el.metadata = {}
    return [el]


def fake_chunk(elements, max_characters=8000, **_kwargs):
    return elements


def test_list_files(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "a.docx").write_text("y")
    proc = DocumentProcessor(partition_pdf_func=fake_partition, partition_docx_func=fake_partition, chunk_func=fake_chunk)
    files = proc.list_files(tmp_path, ["pdf", "docx"])
    assert len(files) == 1
    assert files[0].name in {"a.pdf", "a.docx"}


def test_create_directory(tmp_path: Path) -> None:
    proc = DocumentProcessor(partition_pdf_func=fake_partition, partition_docx_func=fake_partition, chunk_func=fake_chunk)
    new_dir = tmp_path / "nested/dir"
    proc.create_directory(new_dir)
    assert new_dir.exists()


def test_process_file_selects_partition() -> None:
    proc = DocumentProcessor(partition_pdf_func=fake_partition, partition_docx_func=fake_partition, chunk_func=fake_chunk)
    path = Path("file.pdf")
    out = proc.process_file(path, Path("."), Path("."))
    assert out and out[0].page_content == "text"


def test_process_documents_iterates(tmp_path: Path) -> None:
    file1 = tmp_path / "a.pdf"
    file1.write_text("x")
    proc = DocumentProcessor(partition_pdf_func=fake_partition, partition_docx_func=fake_partition, chunk_func=fake_chunk)
    results = proc.process_documents([file1])
    assert len(results) == 1
    assert results[0][0].page_content == "text"
