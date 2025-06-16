"""
Standalone script to (re)build the pgvector index from a directory of files.
Run:
    python -m app.ingestion.ingest /path/to/docs
"""

import asyncio
from pathlib import Path
import sys
from tqdm import tqdm
from openai import AzureAsyncOpenAI
from ..database import get_conn, open_pool_once
from ..config import get_settings
from ..logging import logger

settings = get_settings()
openai_client = AzureAsyncOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version= settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    azure_deployment=settings.OPENAI_MODEL
)

CHUNK_SIZE = 800  # tokens or characters – adapt as needed


def chunk_text(text: str, size: int = CHUNK_SIZE):
    """Naïve chunking by chars; replace with token-aware splitter if desired."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


async def process_file(path: Path):
    # 1. Read text
    text = path.read_text(encoding="utf-8")
    # 2. Insert chunks
    async with get_conn() as cur:
        for chunk in chunk_text(text):
            emb = await openai_client.embeddings.create(
                input=[chunk], model=settings.AZURE_OPENAI_EMBEDDER
            )
            await cur.execute(
                "INSERT INTO documents (filename, content, embedding) VALUES (%s,%s,%s)",
                (path.name, chunk, emb.data[0].embedding),
            )


async def main(directory: str):
    await open_pool_once()
    docs_dir = Path(directory).expanduser().resolve()
    files = list(docs_dir.rglob("*.txt"))
    for file in tqdm(files, desc="Embedding"):
        await process_file(file)
    logger.info("Ingestion complete: %d chunks", len(files))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: ingest.py <directory>")
    asyncio.run(main(sys.argv[1]))
