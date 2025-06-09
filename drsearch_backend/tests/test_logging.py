import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import types

from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
from app.models import LoggingSettings, BlobSettings


def _app(tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/")
    async def root():
        return JSONResponse({"ok": True})

    configure_logging(LoggingSettings(log_dir=tmp_path), BlobSettings())
    return TestClient(app)


def test_request_logged(tmp_path):
    client = _app(tmp_path)
    client.get("/")
    log_file = tmp_path / "info.log"
    assert log_file.exists()
    data = [json.loads(line) for line in log_file.read_text().splitlines()]
    assert any("HTTP request" in d.get("message", "") for d in data)


def test_blob_upload_not_enabled(monkeypatch, tmp_path):
    called = False

    def dummy(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.core.logging.Thread", lambda *a, **k: types.SimpleNamespace(start=dummy)
    )
    configure_logging(
        LoggingSettings(log_dir=tmp_path, log_to_blob=False),
        BlobSettings(connection_string="c", container="cont"),
    )
    assert not called
