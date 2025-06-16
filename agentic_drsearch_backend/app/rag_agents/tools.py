"""
Tool functions exposed to the OpenAI agent.
Each tool must be decorated with @function_tool.
"""
from typing import List, Literal

from agents import function_tool
from langchain_openai import AzureOpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy
from openai import AsyncAzureOpenAI

from ..config import get_settings
from ..logging import logger

settings = get_settings()

openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    azure_deployment=settings.AZURE_OPENAI_EMBEDDER,
)


@function_tool
async def search_documents(
    query: str,
    top_k: int = 3,
    distance_metric: Literal["cosine", "euclidean"] = "cosine",
) -> str:
    """
    Vector similarity search over the pgvector index.

    Args:
        query: Raw user query string.
        top_k: Number of chunks to return.
        distance_metric: 'cosine' or 'euclidean'.

    Returns:
        Concatenated document snippets wrapped in <doc> tags, suitable
        for direct ingestion by the agent.
        Example:
            <doc id="0" source="policy.pdf">...</doc>
            <doc id="1" source="manual.md">...</doc>
    """
    # 1. Initialise embedding model and vector store
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_deployment=settings.AZURE_OPENAI_EMBEDDER,
        async_client=openai_client,
    )
    store = PGVector(
        embeddings=embeddings,
        connection=settings.PGVECTOR_URL,
        collection_name=settings.PGVECTOR_INDEX,
        async_mode=True,
        distance_strategy=(
            DistanceStrategy.EUCLIDEAN
            if distance_metric == "euclidean"
            else DistanceStrategy.COSINE
        ),
    )

    # 2. Run similarity search via PGVector
    docs = await store.asimilarity_search(query=query, k=top_k)

    # 3. Format result
    snippets: List[str] = []
    for idx, doc in enumerate(docs):
        filename = doc.metadata.get("filename", "unknown")
        snippet = doc.page_content[:1000].replace("\n", " ")
        snippets.append(f'<doc id="{idx}" source="{filename}">{snippet}</doc>')

    joined = "\n".join(snippets)
    logger.debug("search_documents returned %d docs", len(docs))
    return joined
