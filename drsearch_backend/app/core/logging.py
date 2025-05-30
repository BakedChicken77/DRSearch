"""Application-wide structured logging utilities."""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:  # optional dependency
    from azure.storage.blob import BlobServiceClient
except Exception:  # pragma: no cover - azure not installed
    BlobServiceClient = None  # type: ignore

from pythonjsonlogger import jsonlogger

from app.models import BlobSettings, LoggingSettings


class _LevelFilter(logging.Filter):
    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        return record.levelno == self.level


class _JsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):  # noqa: D401
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname


_listener: logging.handlers.QueueListener | None = None


def _start_blob_uploader(
    directory: Path, settings: LoggingSettings, blob: BlobSettings | None
) -> None:
    if not settings.to_blob or blob is None:
        return
    if BlobServiceClient is None:
        logging.getLogger(__name__).warning(
            "azure-storage-blob not installed; skipping blob upload"
        )
        return

    def _worker() -> None:
        try:
            client = BlobServiceClient.from_connection_string(blob.connection_string)
        except Exception as exc:  # pragma: no cover - network failures
            logging.getLogger(__name__).warning("Blob connection failed: %s", exc)
            return
        while True:
            time.sleep(settings.blob_upload_interval_sec)
            for path in directory.glob("*.jsonl*"):
                blob_name = f"logs/{blob.container}/{path.name}"
                try:
                    with open(path, "rb") as f:
                        client.get_blob_client(
                            container=blob.container, blob=blob_name
                        ).upload_blob(f, overwrite=True)
                except Exception as exc:  # pragma: no cover - network
                    logging.getLogger(__name__).warning(
                        "Failed to upload log %s: %s", path, exc
                    )

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def configure_logging(
    settings: LoggingSettings,
    blob: BlobSettings | None = None,
    *,
    component: str = "backend",
) -> None:
    """Set up structured logging according to ``settings``."""

    global _listener

    base = Path("logs") / settings.level.lower()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_dir = base / today / component
    log_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.file_max_mb * 1024 * 1024
    fmt = _JsonFormatter("%(asctime)s %(name)s %(message)s")

    handlers: list[logging.Handler] = []
    for level_name in ["INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL"]:
        level = getattr(logging, level_name)
        handler = logging.handlers.RotatingFileHandler(
            log_dir / f"{level_name.lower()}.jsonl",
            maxBytes=max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.addFilter(_LevelFilter(level))
        handler.setFormatter(fmt)
        handlers.append(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    handlers.append(console)

    q: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(q)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.level.upper(), logging.INFO))
    root.addHandler(queue_handler)

    if _listener:
        _listener.stop()
    _listener = logging.handlers.QueueListener(q, *handlers, respect_handler_level=True)
    _listener.start()

    _start_blob_uploader(log_dir, settings, blob)
