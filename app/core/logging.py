# file: app/core/logging.py


"""Structured JSON logging configured at import‑time."""

from __future__ import annotations

import logging
import sys
from types import FrameType
from typing import Any, Dict

from pythonjsonlogger import jsonlogger


class _CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Adds the log‑level name as *level* and keeps the message field."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, _message_dict: Dict[str, Any]) -> None:  # noqa: D401,E501 – override
        super().add_fields(log_record, record, _message_dict)
        log_record["level"] = record.levelname


def configure_logging(level: int = logging.INFO) -> None:  # pragma: no cover
    """Initialise *root* logger so downstream modules get structured output.

    Args:
        level: Minimum severity to emit. Defaults to :pymod:`logging.INFO`.
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_CustomJsonFormatter("%(level)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
