"""Command line utilities for managing pgvector indexes."""

import argparse
import logging
import os
from typing import Any

import sqlalchemy
from sqlalchemy import text
from langchain_community.vectorstores.pgvector import PGVector

from app.chain.embeddings import EmbeddingFactory
from scripts import transfer_weaviate_to_pgvector as transfer_script

logger = logging.getLogger(__name__)


def transfer_index(index: str, conn: str, dimension: int) -> None:
    os.environ["INDEX_NAME"] = index
    os.environ["PGVECTOR_URL"] = conn
    os.environ["PGVECTOR_DIMENSION"] = str(dimension)
    transfer_script.main()


def delete_index(index: str, conn: str) -> None:
    store = PGVector(
        connection_string=conn,
        embedding_function=EmbeddingFactory.get(),
        collection_name=index,
        use_jsonb=True,
        create_extension=True,
    )
    store.delete_collection()
    logger.info("Deleted collection '%s'", index)


def list_indexes(conn: str) -> None:
    engine = sqlalchemy.create_engine(conn)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT name FROM langchain_pg_collection"))
        for row in result:
            print(row[0])


def main(argv: Any | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Manage pgvector indexes")
    parser.add_argument(
        "--conn",
        default=os.environ.get("PGVECTOR_URL", ""),
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=int(os.environ.get("PGVECTOR_DIMENSION", "1536")),
        help="Vector dimension for transfer",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transfer", help="Transfer index from Weaviate")
    t.add_argument("index", help="Index name to transfer")

    d = sub.add_parser("delete", help="Delete a pgvector index")
    d.add_argument("index", help="Index name to delete")

    sub.add_parser("list", help="List pgvector indexes")

    args = parser.parse_args(argv)

    if args.cmd == "transfer":
        transfer_index(args.index, args.conn, args.dimension)
    elif args.cmd == "delete":
        delete_index(args.index, args.conn)
    elif args.cmd == "list":
        list_indexes(args.conn)


if __name__ == "__main__":  # pragma: no cover - script entry point
    try:
        main()
    except Exception as exc:  # pragma: no cover - simplified error handling
        logger.error("Operation failed: %s", exc)
        raise
