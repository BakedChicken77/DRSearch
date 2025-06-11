from __future__ import annotations

import asyncio
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Queue
from datetime import datetime
import os

from pythonjsonlogger import jsonlogger

from app.models.logging import LoggingSettings
from app.azure_search_blob_manager.AzureBlobStorageWrapperAsync import AzureBlobStorageAsync

LOG_DIR = Path(os.environ.get("LOG_DIR", Path(__file__).resolve().parents[2] / "app_logs"))
COMPONENT = "backend"

_listener: QueueListener | None = None
_blob_task: asyncio.Task | None = None


def _get_formatter() -> logging.Formatter:
    return jsonlogger.JsonFormatter()


def _setup_handlers(settings: LoggingSettings) -> QueueListener:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = _get_formatter()
    handlers = []
    for level in ("debug", "info", "warning", "error"):
        handler = RotatingFileHandler(
            LOG_DIR / f"{level}.jsonl",
            maxBytes=settings.log_file_max_mb * 1024 * 1024,
            backupCount=settings.log_backup_count,
        )
        handler.setLevel(getattr(logging, level.upper()))
        handler.setFormatter(formatter)
        handlers.append(handler)
    queue: Queue = Queue(-1)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.addHandler(QueueHandler(queue))
    listener = QueueListener(queue, *handlers)
    return listener


async def _upload_logs(settings: LoggingSettings, storage: AzureBlobStorageAsync) -> None:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    env = os.getenv("NODE_ENV", "dev")
    for file in LOG_DIR.glob("*.jsonl"):
        blob_path = f"logs/{env}/{date_str}/{COMPONENT}/{file.name}"
        await storage.upload_blob(settings.log_to_blob_container, blob_path, str(file))


async def _periodic_blob_upload(settings: LoggingSettings, storage: AzureBlobStorageAsync) -> None:
    try:
        while True:
            await asyncio.sleep(settings.blob_upload_interval_sec)
            await _upload_logs(settings, storage)
    finally:
        await storage.close()


def _start_blob_uploader(loop: asyncio.AbstractEventLoop, settings: LoggingSettings) -> asyncio.Task:
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


def shutdown_logging() -> None:
    global _listener, _blob_task
    if _listener:
        _listener.stop()
        _listener = None
    if _blob_task:
        _blob_task.cancel()
        _blob_task = None
