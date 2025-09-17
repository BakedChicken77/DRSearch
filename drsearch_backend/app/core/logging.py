from __future__ import annotations

import asyncio
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Queue
from datetime import datetime, timezone
import os
import socket
from typing import Dict

from pythonjsonlogger import jsonlogger

from app.models.logging import LoggingSettings
from app.azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
    AzureBlobStorageAsync,
)

LOG_DIR = Path(
    os.environ.get("LOG_DIR", Path(__file__).resolve().parents[2] / "app_logs")
)
COMPONENT = "backend"

_listener: QueueListener | None = None
_blob_task: asyncio.Task | None = None
_TAIL_OFFSETS: Dict[Path, int] = {}  # in-memory tail positions per file
_INSTANCE_ID = os.getenv("WEBSITE_INSTANCE_ID") or socket.gethostname()
_flush_lock = asyncio.Lock()

class ExcludeFeedbackFilter(logging.Filter):
    """Filter out records from the 'feedback' logger."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - simple filter
        return not record.name.startswith("feedback")


def _get_formatter() -> logging.Formatter:
    return jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        rename_fields={"asctime": "timestamp"}
    )

class DropAzureBlobNoise(logging.Filter):
    """
    Drop INFO/DEBUG from Azure SDK so we don't log every blob request/response.
    Still allow WARNING/ERROR/CRITICAL to pass through.
    """
    AZURE_PREFIXES = (
        "azure.storage.blob",
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.core.pipeline",
        "azure.core",
    )
    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        if record.levelno < logging.WARNING and any(name.startswith(p) for p in self.AZURE_PREFIXES):
            return False
        return True

def _setup_handlers(settings: LoggingSettings) -> QueueListener:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = _get_formatter()
    handlers = []

    # General backend log file
    backend_handler = RotatingFileHandler(
        LOG_DIR / "drsearch_backend_log.jsonl",
        maxBytes=settings.log_file_max_mb * 1024 * 1024,
        backupCount=settings.log_backup_count,
    )
    backend_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    backend_handler.setFormatter(formatter)
    backend_handler.addFilter(ExcludeFeedbackFilter())
    backend_handler.addFilter(DropAzureBlobNoise())   # ⬅️ add this
    handlers.append(backend_handler)

    # Feedback log file
    feedback_handler = RotatingFileHandler(
        LOG_DIR / "feedback.jsonl",
        maxBytes=settings.log_file_max_mb * 1024 * 1024,
        backupCount=settings.log_backup_count,
    )
    feedback_handler.setLevel(logging.INFO)
    feedback_handler.setFormatter(formatter)
    feedback_handler.addFilter(logging.Filter("feedback"))
    handlers.append(feedback_handler)

    queue: Queue = Queue(-1)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.addHandler(QueueHandler(queue))

    # ⬇️ Clamp Azure SDK logs to WARNING+ so only issues get through
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    listener = QueueListener(queue, *handlers)
    return listener


def _iter_log_files():
    # Include rotated segments (e.g., .jsonl.1, .jsonl.2). Only JSONL logs.
    yield from LOG_DIR.glob("*.jsonl*")


async def _append_logs_once(settings: LoggingSettings, storage: AzureBlobStorageAsync) -> None:
    """
    Append only new bytes (since last read) from each local log file to an
    Append Blob named by day/component/instance/filename. Safe across redeploys.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    env = os.getenv("NODE_ENV", "dev")

    for fpath in _iter_log_files():
        try:
            # Local file may disappear between glob and stat on rotations.
            stat = fpath.stat()
            size = stat.st_size
        except FileNotFoundError:
            _TAIL_OFFSETS.pop(fpath, None)
            continue

        last = _TAIL_OFFSETS.get(fpath, None)
        # If file truncated/rotated (size < last), resume from 0.
        if last is not None and size < last:
            # file truncated or rotated; restart at 0 for this file
            last = 0

        # Build blob path including instance id to avoid mixing logs across machines
        blob_path = f"logs/{env}/{date_str}/{COMPONENT}/{_INSTANCE_ID}/{fpath.name}"
        container = settings.log_to_blob_container

        # Ensure append blob exists
        await storage.ensure_append_blob(container, blob_path, content_type="application/json")

        # Seed initial offset from remote blob length to avoid duplicate appends after restarts
        if last is None:
            try:
                remote_len = await storage.get_blob_length(container, blob_path)
            except Exception:
                remote_len = 0
            # If remote is longer than local file (e.g., local just rotated), start at 0.
            last = remote_len if remote_len <= size else 0

        # Nothing new to send?
        if size == last:
            _TAIL_OFFSETS[fpath] = last
            continue

        # Read only the new tail and append
        try:
            with fpath.open("rb") as fh:
                fh.seek(last)
                chunk = fh.read(size - last)
        except OSError:
            continue

        await storage.append_blob_bytes(container, blob_path, chunk)
        _TAIL_OFFSETS[fpath] = size



async def _periodic_blob_upload(
    settings: LoggingSettings, storage: AzureBlobStorageAsync
) -> None:
    try:
        # Upload immediately on startup, then at interval.
        while True:
            await _append_logs_once(settings, storage)
            await asyncio.sleep(settings.blob_upload_interval_sec)
    finally:
        await storage.close()


def _start_blob_uploader(
    loop: asyncio.AbstractEventLoop, settings: LoggingSettings
) -> asyncio.Task:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        return loop.create_task(asyncio.sleep(0))
    storage = AzureBlobStorageAsync(conn)
    return loop.create_task(_periodic_blob_upload(settings, storage))


def configure_logging() -> None:
    global _listener, _blob_task
    settings = LoggingSettings()
    listener = _setup_handlers(settings)
    listener.start()
    _listener = listener
    if settings.log_output_mode in {"blob", "both"}:
        loop = asyncio.get_event_loop()
        _blob_task = _start_blob_uploader(loop, settings)

async def _flush_once_for_shutdown(settings: LoggingSettings, storage: AzureBlobStorageAsync) -> None:
    async with _flush_lock:
        try:
            await _append_logs_once(settings, storage)
        except Exception:
            pass

def shutdown_logging() -> None:
    global _listener, _blob_task
    if _listener:
        _listener.stop()
        _listener = None
    if _blob_task:
        # best-effort final flush
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                settings = LoggingSettings()
                conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                if conn and (settings.log_output_mode in {"blob", "both"}):
                    storage = AzureBlobStorageAsync(conn)
                    loop.run_until_complete(_flush_once_for_shutdown(settings, storage))
        except Exception:
            pass
        _blob_task.cancel()
        _blob_task = None
