"""Helpers to render retrieved documents into prompt-ready XML."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import logging
from typing import Sequence

from langchain_community.document_transformers import LongContextReorder
from langchain.schema import Document

from app.chain.mapping import PartNumberMapping
from app.core import chain_config


logger = logging.getLogger(__name__)
@dataclass
class _FragmentState:
    total_chars: int = 0
    has_existing: bool = False


class DocumentFormatter:  # pylint: disable=too-few-public-methods
    """Utility to pretty-print retrieved docs and enrich with UNC paths."""

    def __init__(self, mapping: PartNumberMapping, max_chars: int | None = None):
        self._mapping = mapping.data
        self._reorder = LongContextReorder() if chain_config.RAG_ON else None
        limit = max_chars
        if limit is None:
            limit = chain_config.CONTEXT_CHAR_LIMIT
        self._max_chars = limit if limit and limit > 0 else None

    def __call__(self, docs: Sequence[Document]) -> str:
        """Return prompt-ready <doc/> XML fragments."""
        prepared_docs = self._prepare_documents(docs)
        use_html = self._should_use_html(prepared_docs)

        formatted: list[str] = []
        state = _FragmentState()
        for idx, doc in enumerate(prepared_docs):
            fragment, added_chars = self._render_fragment(
                doc,
                idx,
                use_html=use_html,
                state=state,
            )
            if fragment is None:
                break
            formatted.append(fragment)
            state.total_chars += added_chars
            state.has_existing = True

        return "\n".join(formatted)

    def _prepare_documents(self, docs: Sequence[Document]) -> list[Document]:
        """Deduplicate by content and reorder if enabled."""

        unique_map = OrderedDict()
        for doc in docs:
            if doc.page_content not in unique_map:
                unique_map[doc.page_content] = doc
        unique_docs = list(unique_map.values())
        return (
            self._reorder.transform_documents(unique_docs)
            if self._reorder
            else unique_docs
        )

    def _should_use_html(self, docs: Sequence[Document]) -> bool:
        if self._max_chars is None:
            return True

        html_chars = self._estimate_total_chars(docs, prefer_html=True)
        if html_chars <= self._max_chars:
            return True

        logger.info(
            "HTML context (%s chars) exceeds limit (%s); falling back to plain text",
            html_chars,
            self._max_chars,
        )
        return False

    def _render_fragment(
        self,
        doc: Document,
        idx: int,
        *,
        use_html: bool,
        state: _FragmentState,
    ) -> tuple[str | None, int]:
        filename = doc.metadata.get("filename", "Unknown part number")
        if self._mapping and filename in self._mapping:
            doc.metadata["file_path"] = self._mapping[filename]

        preferred = doc.metadata.get("text_as_html") if use_html else None
        content = preferred or doc.page_content

        prefix = f"<doc id='{idx}' source='{filename}'>"
        suffix = "</doc>"
        newline_overhead = 1 if state.has_existing else 0

        if self._max_chars is not None:
            remaining = self._max_chars - state.total_chars - newline_overhead
            if remaining <= 0:
                return None, 0

            max_content = remaining - len(prefix) - len(suffix)
            if max_content <= 0:
                return None, 0

            if len(content) > max_content:
                content = content[:max_content]

        fragment = f"{prefix}{content}{suffix}"
        added_chars = len(fragment) + newline_overhead
        return fragment, added_chars

    @staticmethod
    def _estimate_total_chars(
        docs: Sequence[Document],
        *,
        prefer_html: bool,
    ) -> int:
        """Estimate the final number of characters if all docs were rendered."""

        if not docs:
            return 0

        total = 0
        for idx, doc in enumerate(docs):
            filename = doc.metadata.get("filename", "Unknown part number")
            prefix = f"<doc id='{idx}' source='{filename}'>"
            suffix = "</doc>"
            if prefer_html and doc.metadata.get("text_as_html"):
                content = doc.metadata["text_as_html"]
            else:
                content = doc.page_content
            total += len(prefix) + len(content) + len(suffix)

        total += len(docs) - 1  # newline separators
        return total
