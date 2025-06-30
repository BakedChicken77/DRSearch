import json
import logging
import asyncio  # type: ignore
from pathlib import Path
import os

os.environ["LOG_OUTPUT_MODE"] = "local"
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from fastapi.testclient import TestClient  # type: ignore
from app import create_app
import importlib
from app import core as core_pkg


def test_local_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_OUTPUT_MODE", "local")
    importlib.reload(core_pkg.logging)
    asyncio.set_event_loop(asyncio.new_event_loop())
    core_pkg.logging.configure_logging()
    logger = logging.getLogger("test")
    logger.info("hello", extra={"foo": "bar"})
    core_pkg.logging.shutdown_logging()
    lines = [
        json.loads(l)
        for l in (tmp_path / "drsearch_backend_log.jsonl").read_text().splitlines()
    ]
    data = next(item for item in lines if item.get("message") == "hello")
    assert data["message"] == "hello"
    assert data["foo"] == "bar"


def test_logging_middleware(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_OUTPUT_MODE", "local")
    importlib.reload(core_pkg.logging)
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app()
    client = TestClient(app)
    client.get("/index-options")
    core_pkg.logging.shutdown_logging()
    lines = [
        json.loads(l)
        for l in (tmp_path / "drsearch_backend_log.jsonl").read_text().splitlines()
    ]
    record = next(item for item in lines if item.get("path") == "/index-options")
    assert record["path"] == "/index-options"
    assert "latency" in record


def test_blob_upload_task_started(monkeypatch):
    called = {}

    def dummy(loop, settings):
        called["yes"] = True
        return asyncio.get_event_loop().create_task(asyncio.sleep(0))

    monkeypatch.setenv("LOG_OUTPUT_MODE", "blob")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    importlib.reload(core_pkg.logging)
    asyncio.set_event_loop(asyncio.new_event_loop())
    monkeypatch.setattr(core_pkg.logging, "_start_blob_uploader", dummy)
    core_pkg.logging.configure_logging()
    assert called.get("yes")
    core_pkg.logging.shutdown_logging()
