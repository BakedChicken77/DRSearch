"""Create or update a part-number mapping table from a CSV file."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from app.chain.mapping import create_mapping_table_from_csv

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    conn_str = os.environ.get("PGVECTOR_URL")
    if not conn_str:
        raise EnvironmentError("PGVECTOR_URL must be set")

    parser = argparse.ArgumentParser(
        description="Load CSV data into a PostgreSQL mapping table"
    )
    parser.add_argument("csv", help="Path to CSV file with mapping entries")
    parser.add_argument("table", help="Target PostgreSQL table name")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    create_mapping_table_from_csv(csv_path, conn_str, args.table)
    logger.info("Mapping table '%s' updated from %s", args.table, csv_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script entry point
        logger.error("Failed to create mapping table: %s", exc)
        raise
