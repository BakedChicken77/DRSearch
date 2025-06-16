"""
Tool functions exposed to the OpenAI agent.
Each tool must be decorated with @function_tool.
"""

from typing import List, Literal
from agents import function_tool
from openai import AsyncOpenAI

from ..config import get_settings
from ..database import get_conn
from ..logging import logger

settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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
    # 1. Embed the query
    embed_resp = await openai_client.embeddings.create(
        input=[query], model="text-embedding-ada-002"
    )
    embedding = embed_resp.data[0].embedding

    # 2. Build SQL
    op = "<->" if distance_metric == "euclidean" else "<=>"
    sql = (
        f"SELECT id, filename, content "
        f"FROM documents "
        f"ORDER BY embedding {op} %s LIMIT %s"
    )

    # 3. Run query
    async with get_conn() as cur:
        await cur.execute(sql, (embedding, top_k))
        rows = await cur.fetchall()

    # 4. Format result
    snippets: List[str] = []
    for idx, (_, filename, content) in enumerate(rows):
        snippet = content[:1000].replace("\n", " ")
        snippets.append(f'<doc id="{idx}" source="{filename}">{snippet}</doc>')

    joined = "\n".join(snippets)
    logger.debug("search_documents returned %d docs", len(rows))
    return joined
