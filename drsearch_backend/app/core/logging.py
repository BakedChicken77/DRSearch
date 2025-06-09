from __future__ import annotations

import asyncio
import logging
import logging.handlers as handlers
import sys
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Event, Thread

from pythonjsonlogger import jsonlogger

from app.models import BlobSettings, LoggingSettings

try:  # optional external wrapper
    from azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
        AzureBlobStorageAsync,
    )
except Exception:  # pragma: no cover - fallback
    from azure.storage.blob.aio import BlobServiceClient

    class AzureBlobStorageAsync:  # type: ignore
        def __init__(self, connection_string: str):
            self._client = BlobServiceClient.from_connection_string(connection_string)

        async def upload_blob(self, container: str, blob: str, path: str) -> None:
            blob_client = self._client.get_blob_client(container, blob)
            with open(path, "rb") as f:
                await blob_client.upload_blob(f, overwrite=True)

        async def close(self) -> None:
            await self._client.close()


class _CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record.setdefault("message", record.getMessage())


def _uploader(
    log_dir: Path, settings: LoggingSettings, blob: BlobSettings, stop: Event
) -> None:
    async def _upload_once():
        storage = AzureBlobStorageAsync(blob.connection_string)
        date = datetime.utcnow().strftime("%Y-%m-%d")
        for file in log_dir.glob("*.log"):
            blob_name = f"logs/{settings.log_level}/{date}/{file.name}"
            await storage.upload_blob(blob.container, blob_name, str(file))
        await storage.close()

    while not stop.wait(settings.blob_upload_interval_sec):
        try:
            asyncio.run(_upload_once())
        except Exception:
            logging.getLogger(__name__).exception("Failed to upload logs")


def configure_logging(
    logging_settings: LoggingSettings, blob_settings: BlobSettings | None = None
) -> None:
    level = getattr(logging, logging_settings.log_level.upper(), logging.INFO)
    queue: Queue = Queue(-1)
    queue_handler = handlers.QueueHandler(queue)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(queue_handler)

    log_dir = logging_settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = _CustomJsonFormatter()
    file_info = handlers.RotatingFileHandler(
        log_dir / "info.log",
        maxBytes=logging_settings.log_file_max_mb * 1024 * 1024,
        backupCount=logging_settings.log_backup_count,
    )
    file_info.setLevel(logging.INFO)
    file_info.setFormatter(fmt)

    file_error = handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=logging_settings.log_file_max_mb * 1024 * 1024,
        backupCount=logging_settings.log_backup_count,
    )
    file_error.setLevel(logging.ERROR)
    file_error.setFormatter(fmt)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)

    listener = handlers.QueueListener(
        queue, stream, file_info, file_error, respect_handler_level=True
    )
    listener.daemon = True
    listener.start()

    if (
        logging_settings.log_to_blob
        and blob_settings
        and blob_settings.connection_string
        and blob_settings.container
    ):
        stop_event = Event()
        thread = Thread(
            target=_uploader,
            args=(log_dir, logging_settings, blob_settings, stop_event),
            daemon=True,
        )
        thread.start()
