"""Document processing entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, IO

from dotenv import load_dotenv

from document_processor import DocumentProcessor

load_dotenv()

PROCESSOR = DocumentProcessor()


def process_file(
    file_path: Path,
    base_dir: Path,
    elements_dir: Path,
    json_path: Optional[Path] = None,
    max_chunk_size: int = 8000,
    *,
    input_file: Optional[IO[bytes]] = None,
    module_logs: bool = False,
    html_summaries: bool = False,
) -> list:
    """Proxy to :class:`DocumentProcessor.process_file`."""
    return PROCESSOR.process_file(
        file_path=file_path,
        base_dir=base_dir,
        elements_dir=elements_dir,
        json_path=json_path,
        max_chunk_size=max_chunk_size,
        input_file=input_file,
        module_logs=module_logs,
        html_summaries=html_summaries,
    )


def process_documents(
    files: Iterable[Path],
    *,
    max_chunk_size: int = 8000,
) -> List[list]:
    """Proxy to :class:`DocumentProcessor.process_documents`."""
    return PROCESSOR.process_documents(files, max_chunk_size=max_chunk_size)


if __name__ == "__main__":  # pragma: no cover
    process_documents([Path("docs")])
