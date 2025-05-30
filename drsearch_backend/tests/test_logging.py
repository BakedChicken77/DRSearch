import io
import logging
import types
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
from app.models import LoggingSettings


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):  # noqa: D401
        self.records.append(record)


def test_configure_logging_creates_queue_handler(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.logging.BlobServiceClient", None)
    settings = LoggingSettings(level="INFO", file_max_mb=1, backup_count=1)
    configure_logging(settings, blob=None, component="test")
    root = logging.getLogger()
    assert any(isinstance(h, logging.handlers.QueueHandler) for h in root.handlers)


def test_logging_middleware_logs(monkeypatch):
    handler = ListHandler()
    logging.getLogger("request").addHandler(handler)
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/ping")

    assert any(r.msg == "request" for r in handler.records)
    logging.getLogger("request").removeHandler(handler)
