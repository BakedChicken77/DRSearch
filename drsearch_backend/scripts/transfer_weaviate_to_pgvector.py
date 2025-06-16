#!/usr/bin/env python
"""Transfer data from Weaviate to a pgvector collection (interactive index selection)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Sequence

import weaviate
from langchain_community.vectorstores.pgvector import PGVector

from app.index_config import INDEX_CONFIG
from scripts.create_pgvector_index import create_collection_if_missing

logger = logging.getLogger(__name__)

_PRE_DELETE_COLLECTION = True
_WEAVIATE_URL = "http://localhost:8080"  # or os.getenv("WEAVIATE_URL")


def _configure_logging() -> None:
    """Configure module logging from environment."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _extract_schema(
    client: weaviate.Client,
    class_name: str,
    text_key: str,
) -> tuple[list[str], dict[str, dict]]:
    """
    Pull the class schema directly from Weaviate and return:
      - attrs  : list of non-text_key property names
      - config : dict mapping property → schema details
    """
    class_schema = client.schema.get(class_name)
    if not class_schema:
        raise ValueError(f"Class '{class_name}' not found in Weaviate schema")

    attrs: list[str] = []
    config: dict[str, dict] = {}
    for prop in class_schema.get("properties", []):
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


def _choose_index(client: weaviate.Client) -> str:
    """Interactively select or validate the target Weaviate class (index)."""
    schema = client.schema.get()
    classes = [c["class"] for c in schema.get("classes", [])]
    if not classes:
        raise RuntimeError("No classes found in Weaviate schema.")

    # Command-line argument override
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in classes:
            return arg
        print(f"Provided index '{arg}' not found.\n")

    # Interactive prompt
    while True:
        print("Available Weaviate classes:")
        for i, name in enumerate(classes, start=1):
            print(f"  {i}. {name}")
        choice = input("Select an index by number or name: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(classes):
                return classes[idx - 1]
        elif choice in classes:
            return choice
        print(f"Invalid selection: '{choice}'. Please try again.\n")


def main() -> None:
    _configure_logging()

    # connect
    client = weaviate.Client(
        url=_WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(os.getenv("WEAVIATE_API_KEY", "")),
    )
    logger.info("Connected to Weaviate at %s", _WEAVIATE_URL)

    # choose index/class
    index_name = _choose_index(client)
    logger.info("Using index/class '%s' for transfer", index_name)

    # load index config
    cfg = INDEX_CONFIG.get(index_name)
    if cfg is None:
        raise ValueError(f"Index '{index_name}' not defined in INDEX_CONFIG")

    # prepare PGVector
    conn_str = os.environ["PGVECTOR_URL"]
    dimension = int(os.getenv("PGVECTOR_DIMENSION", "1536"))
    store = create_collection_if_missing(
        conn_str,
        index_name,
        dimension,
        pre_delete_collection=_PRE_DELETE_COLLECTION,
    )
    logger.debug("PGVector collection '%s' ready", index_name)

    # dynamic schema pull
    attrs, schema_cfg = _extract_schema(client, index_name, cfg["index_key"])
    logger.debug("Schema loaded with %s attributes", len(attrs))

    # fetch & upload
    docs = _fetch_weaviate_docs(client, index_name, cfg["index_key"], attrs)
    logger.info("Fetched %s documents from Weaviate", len(docs))
    _upload_docs(store, docs, cfg["index_key"], attrs, schema_cfg)
    logger.info("Transfer complete: %s documents uploaded", len(docs))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("Transfer failed: %s", exc)
        raise
