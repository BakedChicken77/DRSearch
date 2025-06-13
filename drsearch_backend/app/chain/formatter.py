# file: app/chain/formatter.py

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from langchain_community.document_transformers import LongContextReorder
from langchain.schema import Document

from app.chain.mapping import PartNumberMapping
from app.core import chain_config


class DocumentFormatter:
    """Utility to pretty-print retrieved docs and enrich with UNC paths."""

    def __init__(self, mapping: PartNumberMapping):
        self._mapping = mapping.data
        self._reorder = LongContextReorder() if chain_config.RAG_ON else None

    def __call__(self, docs: Sequence[Document]) -> str:
        """Return prompt-ready <doc/> XML fragments."""
        unique_map = OrderedDict()
        for d in docs:
            if d.page_content not in unique_map:
                unique_map[d.page_content] = d
        unique_docs = list(unique_map.values())
        docs_reordered = (
            self._reorder.transform_documents(unique_docs) if self._reorder else unique_docs
        )

        formatted: list[str] = []
        for idx, doc in enumerate(docs_reordered):
            filename = doc.metadata.get("filename", "Unknown part number")
            if self._mapping and filename in self._mapping:
                doc.metadata["file_path"] = self._mapping[filename]
            formatted.append(f"<doc id='{idx}' source='{filename}'>{doc.page_content}</doc>")

        return "\n".join(formatted)
