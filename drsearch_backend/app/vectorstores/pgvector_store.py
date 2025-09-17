from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Dict, List, Tuple, Optional

import psycopg2
from langchain.schema import Document

from langchain_community.vectorstores.pgvector import PGVector
from langchain.schema.retriever import BaseRetriever

from app.chain.embeddings import EmbeddingFactory
from app.core import chain_config
from app.index_config import INDEX_CONFIG

from . import VectorStore

logger = logging.getLogger(__name__)

class PgVectorStore(VectorStore):
    """Vector store backed by PostgreSQL with pgvector, with batched page expansion & consolidation."""

    def __init__(self, index_name: str) -> None:
        cfg = INDEX_CONFIG[index_name]
        attrs = list(cfg["attributes"])
        # Ensure we always request filename and page_number for pagination/merging logic
        for extra in ("filename", "page_number"):
            if extra not in attrs:
                attrs.append(extra)
        self._attributes: Iterable[str] = attrs
        self._collection_name = index_name
        self._store = PGVector(
            connection_string=chain_config._PGVECTOR_URL,
            embedding_function=EmbeddingFactory.get(),
            collection_name=index_name,
        )

    @staticmethod
    def _convert_filter(where: dict[str, Any] | None) -> dict[str, Any] | None:
        """Translate Weaviate-style filters to PGVector format."""
        if not where:
            return None

        op = where.get("operator")
        path = where.get("path")
        if op == "Equal" and isinstance(path, list) and path:
            field = path[0]
            for key in (
                "valueBoolean",
                "valueText",
                "valueString",
                "valueInt",
                "valueNumber",
            ):
                if key in where:
                    return {field: {"$eq": where[key]}}
        return where

    def as_retriever(self, search_kwargs: dict[str, Any]) -> BaseRetriever:
        """Return retriever with normalized filters and consolidated/expanded metadata output."""
        kw = dict(search_kwargs)
        if "where_filter" in kw:
            kw["filter"] = self._convert_filter(kw.pop("where_filter"))

        base = self._store.as_retriever(search_kwargs=kw)
        allowed = set(self._attributes)

        def _strip(docs: List[Document]) -> List[Document]:
            for doc in docs:
                doc.metadata = {k: v for k, v in doc.metadata.items() if k in allowed}
            return docs

        def _consolidate_and_expand(docs: List[Document]) -> List[Document]:
            """
            Consolidate per filename:
              - If _PAGE_WINDOW == -1: no consolidation, no expansion (return stripped docs sorted by filename/page).
              - If _PAGE_WINDOW >= 0: for each filename, compute min/max page across hits,
                expand to [min - window, max + window], fetch that *full* range from DB in one SQL per filename,
                then merge all pages into a single Document per filename (ordered).
              - If pages or filename are missing, those docs pass through as-is.
            """
            window = chain_config._PAGE_WINDOW

            # Collect docs by filename, record page numbers where available.
            hits_by_file: Dict[str, List[Tuple[Optional[int], Document]]] = {}
            passthrough: List[Document] = []
            for d in docs:
                fname = d.metadata.get("filename")
                page = d.metadata.get("page_number")
                # Normalize page to int if possible (some pipelines store as str)
                if isinstance(page, str) and page.isdigit():
                    page = int(page)
                if fname is None or not isinstance(page, int):
                    # Missing info: we can't consolidate/expand these; pass through.
                    passthrough.append(d)
                    continue
                hits_by_file.setdefault(fname, []).append((page, d))

            # Short-circuit: PAGE_WINDOW == -1 → return stripped originals, sorted.
            if window == -1:
                out = passthrough + [d for _, d in sum((v for v in hits_by_file.values()), [])]
                # Stable sort: filename, then page
                def sort_key(doc: Document):
                    fn = doc.metadata.get("filename")
                    pn = doc.metadata.get("page_number")
                    # Try to sort page_number ranges sensibly if present
                    if isinstance(pn, str) and "-" in pn:
                        try:
                            start = int(pn.split("-", 1)[0])
                        except Exception:
                            start = 0
                        pn_val = start
                    elif isinstance(pn, int):
                        pn_val = pn
                    else:
                        pn_val = 0
                    return (fn, pn_val)
                out.sort(key=sort_key)
                return out

            # For PAGE_WINDOW >= 0, build range per filename
            ranges: Dict[str, Tuple[int, int]] = {}
            for fname, items in hits_by_file.items():
                pages = [p for p, _ in items]
                min_p, max_p = min(pages), max(pages)
                start = min_p - window
                end = max_p + window
                if start < 0:
                    start = 0
                ranges[fname] = (start, end)

            # Batch fetch pages per filename (single connection reused)
            fetched_by_file = self._fetch_page_ranges_batched(ranges, allowed)

            # Merge each filename's pages into one consolidated Document
            consolidated: List[Document] = []
            for fname, (start, end) in ranges.items():
                pages_docs = fetched_by_file.get(fname, [])
                if not pages_docs:
                    # Fallback: if no rows (e.g., metadata mismatch), merge the hits we have
                    items = sorted(hits_by_file[fname], key=lambda t: t[0])
                    merged_text = "\n\n".join(d.page_content for _, d in items)
                    merged_meta = self._merge_metadata(items[0][1].metadata, allowed)
                    # Represent page range as "start-end" when different, else as int
                    merged_meta["page_number"] = f"{start}-{end}" if start != end else start
                    consolidated.append(Document(page_content=merged_text, metadata=merged_meta))
                    continue

                # Ensure order by page_number
                pages_docs.sort(key=lambda d: (d.metadata.get("filename"), d.metadata.get("page_number", 0)))
                merged_text = "\n\n".join(d.page_content for d in pages_docs)
                # Base metadata from first fetched doc, then reduce to allowed keys
                base_meta = self._merge_metadata(pages_docs[0].metadata, allowed)
                base_meta["filename"] = fname
                base_meta["page_number"] = f"{start}-{end}" if start != end else start
                consolidated.append(Document(page_content=merged_text, metadata=base_meta))

            # Combine consolidated results with passthrough (docs lacking filename/page)
            # Sort consolidated by filename then range start
            def start_page_of(meta_val):
                if isinstance(meta_val, int):
                    return meta_val
                if isinstance(meta_val, str) and "-" in meta_val:
                    try:
                        return int(meta_val.split("-", 1)[0])
                    except Exception:
                        return 0
                return 0

            consolidated.sort(key=lambda d: (d.metadata.get("filename"), start_page_of(d.metadata.get("page_number"))))
            # Passthrough order preserved; append after consolidated
            return consolidated + passthrough

        class _FilteredRetriever(BaseRetriever):
            def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
                docs = base.get_relevant_documents(query, callbacks=run_manager)
                docs = _strip(docs)
                return _consolidate_and_expand(docs)

            async def _aget_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
                docs = await base.aget_relevant_documents(query, callbacks=run_manager)
                docs = _strip(docs)
                return _consolidate_and_expand(docs)

        return _FilteredRetriever()

    def _merge_metadata(self, meta: Dict[str, Any], allowed: set[str]) -> Dict[str, Any]:
        """Return a shallow copy of metadata limited to allowed keys."""
        return {k: v for k, v in dict(meta).items() if k in allowed}

    def _fetch_page_ranges_batched(
        self, filename_ranges: Dict[str, Tuple[int, int]], allowed: set[str]
    ) -> Dict[str, List[Document]]:
        """
        Fetch documents for multiple (filename -> [start,end]) ranges in one DB connection.
        Returns a dict: filename -> ordered list[Document].
        """
        out: Dict[str, List[Document]] = {fn: [] for fn in filename_ranges.keys()}
        if not filename_ranges:
            return out

        try:
            conn = psycopg2.connect(chain_config._PGVECTOR_URL)
            with conn:
                with conn.cursor() as cur:
                    for fname, (start, end) in filename_ranges.items():
                        cur.execute(
                            """
                            SELECT e.document, e.cmetadata
                              FROM public.langchain_pg_embedding e
                              JOIN public.langchain_pg_collection c ON e.collection_id = c.uuid
                             WHERE c.name = %s
                               AND e.cmetadata ->> 'filename' = %s
                               AND (e.cmetadata ->> 'page_number')::int BETWEEN %s AND %s
                             ORDER BY (e.cmetadata ->> 'page_number')::int
                            """,
                            (self._collection_name, fname, start, end),
                        )
                        rows = cur.fetchall()
                        docs: List[Document] = []
                        for doc_text, meta in rows:
                            if isinstance(meta, str):
                                meta = json.loads(meta)
                            meta = {k: v for k, v in meta.items() if k in allowed}
                            # Normalize page_number to int if possible
                            pn = meta.get("page_number")
                            if isinstance(pn, str) and pn.isdigit():
                                meta["page_number"] = int(pn)
                            docs.append(Document(page_content=doc_text, metadata=meta))
                        out[fname] = docs
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("pgvector batched page fetch failed: %s", exc)
            # On failure, return empty lists for all filenames (caller will fallback)
            return {fn: [] for fn in filename_ranges.keys()}
        finally:
            try:
                if "conn" in locals():
                    conn.close()
            except Exception:
                pass

        return out
