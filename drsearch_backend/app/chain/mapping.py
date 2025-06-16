# file: app/chain/mapping.py

from __future__ import annotations

import csv
import logging
import os
from functools import cached_property
from pathlib import Path
from typing import Dict, Optional

import psycopg2
from psycopg2 import sql

from app.core.chain_config import _MAPPING_DIR

logger = logging.getLogger(__name__)


class PartNumberMapping:
    """Lazily loads part-number → file-path lookup tables from PostgreSQL."""

    def __init__(self, table_name: Optional[str]):
        self._table_name = table_name

    @cached_property
    def data(self) -> Dict[str, str] | None:
        """Return the in-memory mapping or ``None`` when unavailable."""
        if not self._table_name:
            return None

        conn_str = os.getenv("PGVECTOR_URL")
        if not conn_str:
            logger.warning("PGVECTOR_URL environment variable not set")
            return None

        try:
            with psycopg2.connect(conn_str) as conn, conn.cursor() as cur:
                query = sql.SQL(
                    "SELECT file_name, downloaded_file FROM {}"
                ).format(sql.Identifier(self._table_name))
                cur.execute(query)
                rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load mapping table '%s': %s", self._table_name, exc)
            return None

        mapping: Dict[str, str] = {file: path for file, path in rows}
        logger.debug("Loaded %d part-number mappings", len(mapping))
        return mapping


def create_mapping_table_from_csv(
    csv_path: Path, conn_str: str, table_name: str
) -> None:
    """Create or update a PostgreSQL mapping table from ``csv_path``."""
    with psycopg2.connect(conn_str) as conn, conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} (" "file_name TEXT PRIMARY KEY, "
                "downloaded_file TEXT)"
            ).format(sql.Identifier(table_name))
        )

        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = [
                (row["file_name"], row["Downloaded File"]) for row in reader
            ]

        cur.executemany(
            sql.SQL(
                "INSERT INTO {} (file_name, downloaded_file) "
                "VALUES (%s, %s) "
                "ON CONFLICT (file_name) DO UPDATE "
                "SET downloaded_file = EXCLUDED.downloaded_file"
            ).format(sql.Identifier(table_name)),
            rows,
        )
        conn.commit()
