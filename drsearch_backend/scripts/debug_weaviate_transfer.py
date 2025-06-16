#!/usr/bin/env python
"""
Debug utility for Weaviate->PGVector transfers.
Shows class existence, schema, counts, and sample docs so you can see
why a class might appear empty when filtered by use4RAG = True.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from textwrap import shorten

import weaviate


def connect() -> weaviate.Client:
    url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY", "")
    logging.info("Connecting to Weaviate at %s", url)
    return weaviate.Client(url=url, auth_client_secret=weaviate.AuthApiKey(api_key))


def get_class_schema(client: weaviate.Client, class_name: str) -> dict | None:
    schema = client.schema.get()
    for cls in schema.get("classes", []):
        if cls["class"] == class_name:
            return cls
    return None


def meta_count(client: weaviate.Client, class_name: str, where: dict | None = None) -> int:
    q = client.query.aggregate(class_name).with_meta_count()
    if where:
        q = q.with_where(where)
    resp = q.do()
    return resp["data"]["Aggregate"][class_name][0]["meta"]["count"]


def sample_docs(client: weaviate.Client, class_name: str, limit: int = 3) -> list[dict]:
    resp = (
        client.query.get(class_name, ["use4RAG"])
        .with_additional(["id"])
        .with_limit(limit)
        .do()
    )
    return resp["data"]["Get"].get(class_name, [])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    class_name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("INDEX_NAME", "JACSKE_Program")

    client = connect()

    cls_schema = get_class_schema(client, class_name)
    if cls_schema is None:
        logging.error("Class '%s' not found in Weaviate schema.", class_name)
        sys.exit(1)

    logging.info("Class '%s' found with %d properties.", class_name, len(cls_schema["properties"]))
    for p in cls_schema["properties"]:
        logging.info("  %-20s type=%s", p["name"], p["dataType"])

    total = meta_count(client, class_name)
    with_flag = meta_count(
        client,
        class_name,
        {"path": ["use4RAG"], "operator": "Equal", "valueBoolean": True},
    )
    logging.info("Total objects         : %d", total)
    logging.info("Objects with use4RAG=T: %d", with_flag)

    logging.info("Sample objects (id / use4RAG):")
    for doc in sample_docs(client, class_name):
        logging.info("  %-40s %s", doc["_additional"]["id"], doc.get("use4RAG"))

    if with_flag == 0 and total > 0:
        logging.warning(
            "Objects exist but none match use4RAG=True – check spelling/casing or data type."
        )


if __name__ == "__main__":
    main()
