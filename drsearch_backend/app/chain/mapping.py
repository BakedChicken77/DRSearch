# file: app/chain/mapping.py

from __future__ import annotations

import csv
import logging
from functools import cached_property
from pathlib import Path
from typing import Dict, Optional

from app.core.chain_config import _MAPPING_DIR

logger = logging.getLogger(__name__)


class PartNumberMapping:
    """Lazily loads part-number → UNC path CSV lookup tables."""

    def __init__(self, csv_filename: Optional[str]):
        self._csv_filename = csv_filename

    @cached_property
    def data(self) -> Dict[str, str] | None:
        """Return the in-memory mapping or None when no file configured."""
        if not self._csv_filename:
            return None

        csv_path = _MAPPING_DIR / self._csv_filename
        if not csv_path.exists():
            logger.warning("Mapping CSV '%s' not found", csv_path)
            return None

        mapping: Dict[str, str] = {}
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                mapping[row["file_name"]] = row["Downloaded File"]
        logger.debug("Loaded %d part-number mappings", len(mapping))
        return mapping
