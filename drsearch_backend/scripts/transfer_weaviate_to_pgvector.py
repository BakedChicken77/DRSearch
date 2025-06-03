"""Transfer data from Weaviate to a pgvector collection."""

from __future__ import annotations

import logging
import os
from typing import Sequence

import weaviate
from langchain_community.vectorstores.pgvector import PGVector

from app.index_config import INDEX_CONFIG
from scripts.create_pgvector_index import create_collection_if_missing

logger = logging.getLogger(__name__)


def _fetch_weaviate_docs(
    client: weaviate.Client, index: str, text_key: str, attrs: Sequence[str]
) -> list[dict]:
    """Return all documents for ``index`` filtered by ``use4RAG``."""
    fields = [text_key, *attrs]
    result = (
        client.query.get(index, fields)
        .with_additional(["id"])
        .with_where({"path": ["use4RAG"], "operator": "Equal", "valueBoolean": True})
        .do()
    )
    return result["data"]["Get"].get(index, [])


def _upload_docs(
    store: PGVector, docs: list[dict], text_key: str, attrs: Sequence[str]
) -> None:
    """Upload documents into the pgvector store."""
    for doc in docs:
        content = doc.get(text_key, "")
        metadata = {a: doc.get(a) for a in attrs}
        store.add_texts([content], metadatas=[metadata], ids=[doc["_additional"]["id"]])


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    index_name = os.getenv(
        "INDEX_NAME", os.getenv("WEAVIATE_INDEX", "SEPs_F_T_C_W_A_V")
    )
    conn_str = os.environ["PGVECTOR_URL"]
    dimension = int(os.getenv("PGVECTOR_DIMENSION", "1536"))

    cfg = INDEX_CONFIG.get(index_name)
    if cfg is None:
        raise ValueError(f"Index '{index_name}' not defined in INDEX_CONFIG")

    client = weaviate.Client(
        url=os.environ["WEAVIATE_URL"],
        auth_client_secret=weaviate.AuthApiKey(os.environ["WEAVIATE_API_KEY"]),
    )

    store = create_collection_if_missing(conn_str, index_name, dimension)

    docs = _fetch_weaviate_docs(client, index_name, cfg["index_key"], cfg["attributes"])
    logger.info("Fetched %s documents from Weaviate", len(docs))

    _upload_docs(store, docs, cfg["index_key"], cfg["attributes"])
    logger.info("Transfer complete: %s documents uploaded", len(docs))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script entry point
        logger.error("Transfer failed: %s", exc)
        raise
