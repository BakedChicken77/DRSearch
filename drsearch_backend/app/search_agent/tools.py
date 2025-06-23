from __future__ import annotations

from typing import List, Optional, Literal

from agents import function_tool

from app.core.chain_config import _DEFAULT_INDEX, _VECTOR_BACKEND
from app.vectorstores.factory import VectorStoreFactory


async def _retrieve(
    query: str,
    top_k: int,
    index_name: str,
    filenames: Optional[List[str]] = None,
) -> List:
    """Fetch documents using the configured vector store."""
    store = VectorStoreFactory.create(index_name)

    def _filename_filter(names: List[str]) -> dict:
        if not names:
            return {}
        if _VECTOR_BACKEND == "pgvector":
            return {"filename": {"$in": names}}
        if len(names) == 1:
            return {
                "operator": "Equal",
                "path": ["filename"],
                "valueText": names[0],
            }
        return {
            "operator": "Or",
            "operands": [
                {"operator": "Equal", "path": ["filename"], "valueText": n}
                for n in names
            ],
        }

    search_kwargs = {"k": top_k}
    if filenames:
        search_kwargs["where_filter"] = _filename_filter(filenames)

    retriever = store.as_retriever(search_kwargs=search_kwargs)
    return await retriever.aget_relevant_documents(query)


def _format_docs(docs: List) -> str:
    snippets: List[str] = []
    for idx, doc in enumerate(docs):
        filename = doc.metadata.get("filename", "unknown")
        snippet = doc.page_content[:1000].replace("\n", " ")
        snippets.append(f'<doc id="{idx}" source="{filename}">{snippet}</doc>')
    return "\n".join(snippets)


@function_tool
async def similarity_search(
    query: str,
    top_k: int = 3,
    index_name: str = _DEFAULT_INDEX,
    distance_metric: Literal["cosine", "euclidean"] = "cosine",
    filenames: Optional[List[str]] = None,
) -> str:
    docs = await _retrieve(query, top_k, index_name, filenames)
    return _format_docs(docs)


@function_tool
async def keyword_search(
    query: str,
    top_k: int = 3,
    index_name: str = _DEFAULT_INDEX,
    filenames: Optional[List[str]] = None,
) -> str:
    docs = await _retrieve(query, top_k, index_name, filenames)
    return _format_docs(docs)


@function_tool
async def hybrid_search(
    query: str,
    top_k: int = 3,
    index_name: str = _DEFAULT_INDEX,
    filenames: Optional[List[str]] = None,
) -> str:
    docs = await _retrieve(query, top_k, index_name, filenames)
    return _format_docs(docs)
