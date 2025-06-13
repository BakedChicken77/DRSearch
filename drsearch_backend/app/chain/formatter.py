# file: app/chain/formatter.py

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from langchain_community.document_transformers import LongContextReorder
from langchain.schema import Document

from app.chain.mapping import PartNumberMapping
from app.core.chain_config import RAG_ON


class DocumentFormatter:
    """Utility to pretty-print retrieved docs and enrich with UNC paths."""

    def __init__(self, mapping: PartNumberMapping):
        self._mapping = mapping.data
        self._reorder = LongContextReorder() if RAG_ON else None

    def __call__(self, docs: Sequence[Document]) -> str:
        """Return prompt-ready <doc/> XML fragments."""
        unique_docs = list(OrderedDict((d.page_content, d) for d in docs).values())
        docs_reordered = (
            self._reorder.transform_documents(unique_docs) if self._reorder else unique_docs
        )

        formatted: list[str] = []
        for idx, doc in enumerate(docs_reordered):
            filename = doc.metadata.get("filename", "Unknown part number")
            if self._mapping and filename in self._mapping:
                doc.metadata["file_path"] = self._mapping[filename]

            content = doc.metadata.get("text_as_html") or doc.page_content
            formatted.append(f"<doc id='{idx}' source='{filename}'>{content}</doc>")

        return "\n".join(formatted)
