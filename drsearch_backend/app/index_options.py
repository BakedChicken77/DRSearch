"""
Central place for dropdown choices and their example questions.
Also builds per-index acronym lookup tables from the pgvector store.
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

from app.core import chain_config

logger = logging.getLogger(__name__)

# Load a list of acronym keys to ignore (case insensitive)
_IGNORE_FILE = Path(__file__).with_name("acronyms_keys_to_ignore.json")
try:
    _IGNORED_ACRONYM_KEYS = {
        k.strip().upper() for k in json.loads(_IGNORE_FILE.read_text())
    }
except Exception:  # pragma: no cover - missing/invalid file
    _IGNORED_ACRONYM_KEYS = set()

# ---------------------------------------------------------------------------
# Acronym helpers


def _is_valid_acronym(key: str, value: str) -> bool:
    """Return True if the acronym key/value pair should be kept."""

    key_clean = key.strip()
    if not key_clean or not value:
        return False
    if key_clean.upper() in _IGNORED_ACRONYM_KEYS:
        return False
    # Remove short keys (2 or fewer characters)
    if len(key_clean) <= 2:
        return False
    # Remove values with disallowed punctuation
    if any(char in value for char in ".(),[]"):
        return False
    # Remove excessively long values compared to key length
    word_count = len(value.split())
    if word_count - len(key_clean) >= 3:
        return False
    # Remove keys with more lowercase than uppercase letters
    upper = sum(c.isupper() for c in key_clean)
    lower = sum(c.islower() for c in key_clean)
    if lower > upper:
        return False
    return True


# Base index option definitions without acronym data
_BASE_INDEX_OPTIONS = [
    {
        "name": "JACSKE_Program",
        "display_name": "JACSKE Program",
        "example_questions": [
            "What should the output power of the TR Module be?",
            "Where in the Receiver‑Transmitter is the XMIT Trigger generated?",
            "What voltages does the Motor Controller supply to the Transmitter‑Receiver?",
            "What is the purpose of the TDMA board?",
        ],
    },
    {
        "name": "SEPs_F_T_C_W_A_V_Summaries",
        "display_name": "SEPS",
        "example_questions": [
            "How do I fill out my timesheet?",
            "How do I request PTO?",
            "I have an idea for a new product. How do I get funding to work on this idea?",
            "How do I add a new part number to Costpoint?",
        ],
    },
    {
        "name": "Adacstest20250205",
        "display_name": "ADACS",
        "example_questions": [
            "What is ADACS?",
            "What are the different systems in ADACS?",
            "TBD",
            "TBD",
        ],
    },
    {
        "name": "TEST_INDEX",
        "display_name": "TEST_INDEX",
        "example_questions": [
            "1",
            "2",
            "3",
            "4",
        ],
    },
]


def _fetch_acronyms(index_name: str) -> Dict[str, str]:
    """Retrieve acronym map for a given index from pgvector."""

    if not chain_config._PGVECTOR_URL:
        return {}
    try:
        with psycopg2.connect(
            chain_config._PGVECTOR_URL, cursor_factory=RealDictCursor
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.cmetadata
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = %s
                    """,
                    (index_name,),
                )
                rows = cur.fetchall()
    except Exception as exc:  # pragma: no cover - connectivity issues
        logger.warning("Unable to fetch acronyms for %s", index_name, exc_info=exc)
        return {}

    acronyms: Dict[str, str] = {}
    for row in rows:
        meta = row.get("cmetadata") or {}
        keys = meta.get("acronym_keys") or []
        values = meta.get("acronym_values") or []
        for k, v in zip(keys, values):
            if _is_valid_acronym(k, v):
                acronyms[k] = v
    return acronyms


def _build_index_options() -> List[Dict]:
    """Combine base options with acronym maps."""

    opts: List[Dict] = []
    for opt in _BASE_INDEX_OPTIONS:
        acronyms = _fetch_acronyms(opt["name"])
        opts.append({**opt, "acronyms": acronyms})
    return opts


# Public constant consumed by the API
INDEX_OPTIONS = _build_index_options()
