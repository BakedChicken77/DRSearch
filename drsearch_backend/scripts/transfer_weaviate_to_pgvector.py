"""Transfer data from Weaviate to a pgvector collection."""

from __future__ import annotations

import json
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
_WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")


def _configure_logging() -> None:
    """Configure module logging from environment."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _load_schema(schema_file: str, text_key: str) -> tuple[list[str], dict[str, dict]]:
    """Load property names and config from a Weaviate schema JSON file.

    Parameters
    ----------
    schema_file: str
        Path to the exported Weaviate schema JSON file.
    text_key: str
        Name of the property that stores the document text. This field is
        excluded from the returned attribute list so it can be stored in the
        ``document`` column rather than metadata.
    """
    with open(schema_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    props = data.get("result", data.get("properties", []))
    logger.debug("Loaded %d schema properties", len(props))
    attrs: list[str] = []
    config: dict[str, dict] = {}
    for prop in props:
        name = prop.get("name")
        if not name:
            continue
        if name != text_key:
            attrs.append(name)
        config[name] = {
            "data_type": prop.get("dataType"),
            "index_filterable": prop.get("indexFilterable"),
            "index_searchable": prop.get("indexSearchable"),
        }
    return attrs, config


def _fetch_weaviate_docs(
    client: weaviate.Client,
    index: str,
    text_key: str,
    attrs: Sequence[str],
    batch_size: int = 100,
) -> list[dict]:
    """Fetch all matching documents (including embeddings) from Weaviate using pagination."""
    fields = [text_key, *attrs]
    all_docs: list[dict] = []
    offset = 0

    while True:
        result = (
            client.query.get(index, fields)
            .with_additional(["id", "vector"])
            .with_where(
                {"path": ["use4RAG"], "operator": "Equal", "valueBoolean": True}
            )
            .with_limit(batch_size)
            .with_offset(offset)
            .do()
        )
        docs = result.get("data", {}).get("Get", {}).get(index) or []
        logger.debug("Fetched %s docs at offset %s", len(docs), offset)
        if not docs:
            break
        all_docs.extend(docs)
        offset += batch_size

    return all_docs


def _upload_docs(
    store: PGVector,
    docs: list[dict],
    text_key: str,
    attrs: Sequence[str],
    schema: dict[str, dict],
) -> None:
    """Upload precomputed embeddings and metadata into the pgvector store in one batch."""
    logger.debug("Uploading %s documents to pgvector", len(docs))
    texts: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for doc in docs:
        texts.append(doc.get(text_key, ""))
        embeddings.append(doc["_additional"]["vector"])
        meta = {a: doc.get(a) for a in attrs}
        # ensure rag flag is present for PGVector filtering
        meta["use4RAG"] = doc.get("use4RAG", True)
        meta["_schema"] = schema
        metadatas.append(meta)
        ids.append(doc["_additional"]["id"])

    store.add_embeddings(
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def main() -> None:
    _configure_logging()

    index_name = os.getenv("INDEX_NAME", os.getenv("WEAVIATE_INDEX", _INDEX2TRANSFER))
    conn_str = os.environ["PGVECTOR_URL"]
    dimension = int(os.getenv("PGVECTOR_DIMENSION", "1536"))
    logger.info(
        "Starting transfer for index '%s' using Weaviate at %s", index_name, _WEAVIATE_URL
    )
    logger.debug("Using index '%s' with dimension %s", index_name, dimension)

    cfg = INDEX_CONFIG.get(index_name)
    if cfg is None:
        raise ValueError(f"Index '{index_name}' not defined in INDEX_CONFIG")

    client = weaviate.Client(
        url=_WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(os.environ["WEAVIATE_API_KEY"]),
    )
    logger.debug("Connected to Weaviate at %s", _WEAVIATE_URL)

    store = create_collection_if_missing(
        conn_str,
        index_name,
        dimension,
        pre_delete_collection=_PRE_DELETE_COLLECTION,
    )
    logger.debug("PGVector collection '%s' ready", index_name)

    schema_file = os.getenv("WEAVIATE_SCHEMA_FILE", r"scripts\weaviate_schema.json")
    logger.debug("Loading schema from %s", schema_file)
    attrs, schema_cfg = _load_schema(schema_file, cfg["index_key"])
    logger.debug("Schema loaded with %s attributes", len(attrs))

    logger.debug("Fetching documents from Weaviate")
    docs = _fetch_weaviate_docs(client, index_name, cfg["index_key"], attrs)
    logger.info("Fetched %s documents from Weaviate", len(docs))

    _upload_docs(store, docs, cfg["index_key"], attrs, schema_cfg)
    logger.info("Transfer complete: %s documents uploaded", len(docs))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script entry point
        logger.error("Transfer failed: %s", exc)
        raise
