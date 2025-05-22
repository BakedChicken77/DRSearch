from __future__ import annotations

"""Utility classes for document processing."""

from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import logging

from pythonjsonlogger import jsonlogger

from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.xlsx import partition_xlsx
from unstructured.chunking.title import chunk_by_title


class DocumentProcessor:
    """High level interface for partitioning and processing documents."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        *,
        partition_pdf_func=partition_pdf,
        partition_docx_func=partition_docx,
        partition_xlsx_func=partition_xlsx,
        chunk_func=chunk_by_title,
    ) -> None:
        self._partition_pdf = partition_pdf_func
        self._partition_docx = partition_docx_func
        self._partition_xlsx = partition_xlsx_func
        self._chunk = chunk_func
        self.logger = logger or self._configure_logger()

    @staticmethod
    def _configure_logger() -> logging.Logger:
        handler = logging.StreamHandler()
        handler.setFormatter(jsonlogger.JsonFormatter())
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.addHandler(handler)
        return logger

    # Public API -------------------------------------------------------------
    def list_files(self, directory: Path, file_types: Sequence[str]) -> List[Path]:
        """Return files in *directory* matching *file_types* without duplicates."""
        files: List[Path] = []
        seen: set[str] = set()
        for suffix in file_types:
            for file in directory.rglob(f"*.{suffix}"):
                base = file.stem
                if base not in seen:
                    seen.add(base)
                    files.append(file)
        return files

    def create_directory(self, path: Path) -> None:
        """Create *path* recursively if needed."""
        path.mkdir(parents=True, exist_ok=True)

    def process_file(
        self,
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
        """Partition *file_path* and return processed elements."""
        if file_path.suffix.lower() == ".pdf":
            elements = self._partition_pdf(file=input_file, filename=str(file_path))
        elif file_path.suffix.lower() == ".docx":
            elements = self._partition_docx(file=input_file, filename=str(file_path))
        elif file_path.suffix.lower() == ".xlsx":
            elements = self._partition_xlsx(file=input_file, filename=str(file_path))
        else:
            raise ValueError("Unsupported file type")

        elements = [e for e in elements if getattr(e, "category", None) not in {"Header", "Footer", "UncategorizedText"}]
        elements = self._chunk(elements=elements, max_characters=max_chunk_size)
        self.logger.info("processed", extra={"file": str(file_path), "count": len(elements)})
        return elements

    def process_documents(
        self,
        files: Iterable[Path],
        *,
        max_chunk_size: int = 8000,
    ) -> List[list]:
        """Process a sequence of files."""
        results: List[list] = []
        for path in files:
            elements = self.process_file(
                file_path=path,
                base_dir=path.parent,
                elements_dir=path.parent,
                max_chunk_size=max_chunk_size,
            )
            results.append(elements)
        return results


