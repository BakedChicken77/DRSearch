"""Create or update a PostgreSQL pgvector collection for DRSearch."""

from __future__ import annotations

import logging
import os

from langchain_community.vectorstores.pgvector import PGVector

from app.chain.embeddings import EmbeddingFactory

logger = logging.getLogger(__name__)


def create_collection_if_missing(
    conn_str: str, collection: str, dimension: int
) -> PGVector:
    """Create the pgvector tables/collection if they do not exist."""
    try:
        store = PGVector(
            connection_string=conn_str,
            embedding_function=EmbeddingFactory.get(),
            embedding_length=dimension,
            collection_name=collection,
            use_jsonb=True,
            create_extension=True,
        )
    except Exception as exc:  # pragma: no cover - thin wrapper
        logger.error("Failed to create collection: %s", exc)
        raise
    logger.info("Collection '%s' ready", collection)
    return store


def load_sample_documents(store: PGVector) -> None:
    """Upload basic sample documents for validation."""
    content = "Sample document for DRSearch"
    metadata = {
        "file_path": "samples/doc1.txt",
        "filename": "doc1.txt",
        "url": "https://example.com/doc1.txt",
        "text_as_html": "<p>Sample document for DRSearch</p>",
        "source": "example",
        "title": "Sample Document",
        "file_directory": "samples",
        "page_content" : "This is the page content"
    }
    try:
        store.add_texts([content], metadatas=[metadata], ids=["1"])
    except Exception as exc:  # pragma: no cover - simple wrapper
        logger.error("Failed to upload sample document: %s", exc)
        raise
    logger.info("Uploaded sample document")


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    conn_str = os.environ.get("PGVECTOR_URL")
    if not conn_str:
        raise EnvironmentError("PGVECTOR_URL must be set")
    collection = os.environ.get("PGVECTOR_COLLECTION", "drsearch")
    dimension = int(os.environ.get("PGVECTOR_DIMENSION", "1536"))

    store = create_collection_if_missing(conn_str, collection, dimension)
    load_sample_documents(store)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script entry point
        logger.error("Failed to set up pgvector: %s", exc)
        raise
