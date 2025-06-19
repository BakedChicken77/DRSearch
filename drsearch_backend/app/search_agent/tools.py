from __future__ import annotations

from typing import List, Optional, Literal

from agents import function_tool
from langchain_openai import AzureOpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy
from openai import AsyncAzureOpenAI
import os

from app.core.chain_config import _PGVECTOR_URL, _DEFAULT_INDEX

openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDER"),
)


def _pgvector_store(index_name: str, distance_metric: str) -> PGVector:
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDER"),
        async_client=openai_client,
    )
    return PGVector(
        embeddings=embeddings,
        connection_string=_PGVECTOR_URL,
        collection_name=index_name,
        async_mode=True,
        distance_strategy=(
            DistanceStrategy.EUCLIDEAN
            if distance_metric == "euclidean"
            else DistanceStrategy.COSINE
        ),
    )


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
    store = _pgvector_store(index_name, distance_metric)
    filter_ = {"filename": {"$in": filenames}} if filenames else None
    docs = await store.asimilarity_search(query=query, k=top_k, filter=filter_)
    return _format_docs(docs)


@function_tool
async def keyword_search(
    query: str,
    top_k: int = 3,
    index_name: str = _DEFAULT_INDEX,
    filenames: Optional[List[str]] = None,
) -> str:
    store = _pgvector_store(index_name, "cosine")
    filter_ = {"filename": {"$in": filenames}} if filenames else None
    docs = await store.asearch(
        query=query,
        search_type="similarity",
        k=top_k,
        filter=filter_,
    )
    return _format_docs(docs)


@function_tool
async def hybrid_search(
    query: str,
    top_k: int = 3,
    index_name: str = _DEFAULT_INDEX,
    filenames: Optional[List[str]] = None,
) -> str:
    store = _pgvector_store(index_name, "cosine")
    filter_ = {"filename": {"$in": filenames}} if filenames else None
    sim_docs = await store.asimilarity_search(query=query, k=top_k, filter=filter_)
    kw_docs = await store.asearch(
        query=query,
        search_type="similarity",
        k=top_k,
        filter=filter_,
    )
    docs = sim_docs + [d for d in kw_docs if d not in sim_docs]
    return _format_docs(docs[:top_k])
