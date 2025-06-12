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

_INDEX2TRANSFER = "SEPS"
_PRE_DELETE_COLLECTION = True
_WEAVIATE_URL="http://localhost:8080" #os.environ["WEAVIATE_URL"]

def _fetch_weaviate_docs(
    client: weaviate.Client, index: str, text_key: str, attrs: Sequence[str], batch_size: int = 100
) -> list[dict]:
    """Fetch all matching documents (including embeddings) from Weaviate using pagination."""
    fields = [text_key, *attrs]
    all_docs: list[dict] = []
    offset = 0

    while True:
        result = (
            client.query.get(index, fields)
            .with_additional(["id", "vector"])
            .with_where({"path": ["use4RAG"], "operator": "Equal", "valueBoolean": True})
            .with_limit(batch_size)
            .with_offset(offset)
            .do()
        )
        docs = result.get("data", {}).get("Get", {}).get(index) or []
        if not docs:
            break
        all_docs.extend(docs)
        offset += batch_size

    return all_docs


def _upload_docs(
    store: PGVector, docs: list[dict], text_key: str, attrs: Sequence[str]
) -> None:
    """Upload precomputed embeddings and metadata into the pgvector store in one batch."""
    texts: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for doc in docs:
        texts.append(doc.get(text_key, ""))
        embeddings.append(doc["_additional"]["vector"])
        metadatas.append({a: doc.get(a) for a in attrs})
        ids.append(doc["_additional"]["id"])

    store.add_embeddings(
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    index_name = os.getenv(
        "INDEX_NAME", os.getenv("WEAVIATE_INDEX", _INDEX2TRANSFER)
    )
    conn_str = os.environ["PGVECTOR_URL"]
    dimension = int(os.getenv("PGVECTOR_DIMENSION", "1536"))

    cfg = INDEX_CONFIG.get(index_name)
    if cfg is None:
        raise ValueError(f"Index '{index_name}' not defined in INDEX_CONFIG")

    client = weaviate.Client(
        url=_WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(os.environ["WEAVIATE_API_KEY"]),
    )

    store = create_collection_if_missing(conn_str, index_name, dimension,pre_delete_collection=_PRE_DELETE_COLLECTION)

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
