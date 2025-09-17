import json
import logging
import asyncio
from pathlib import Path
import os
import types

import importlib
from fastapi.testclient import TestClient

# Set defaults for this test module
os.environ["LOG_OUTPUT_MODE"] = "local"
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from app import create_app
from app import core as core_pkg
from app.models.logging import LoggingSettings


def test_local_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_OUTPUT_MODE", "local")
    importlib.reload(core_pkg.logging)
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
    # Timestamp should exist if formatter includes it
    assert ("asctime" in data) or ("timestamp" in data)


def test_logging_middleware(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_OUTPUT_MODE", "local")
    importlib.reload(core_pkg.logging)
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
    monkeypatch.setattr(core_pkg.logging, "_start_blob_uploader", dummy)
    core_pkg.logging.configure_logging()
    assert called.get("yes")
    core_pkg.logging.shutdown_logging()


def test_append_blob_tailer_appends_and_partitions_by_instance(tmp_path, monkeypatch):
    """
    Verifies new append-blob functionality:
      - Only new bytes are appended (tailing behavior)
      - Rotated files (*.jsonl.1, *.jsonl.2, ...) are included
      - Blob path is partitioned by instance id to avoid cross-writer mixing
      - Initial offset is seeded from remote length to prevent duplicates on restart
    """
    # Arrange environment and paths
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_OUTPUT_MODE", "blob")
    monkeypatch.setenv("NODE_ENV", "dev")
    monkeypatch.setenv("WEBSITE_INSTANCE_ID", "inst-123")
    # ensure no real azure connection is attempted
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")

    # Reload logging to pick env vars
    importlib.reload(core_pkg.logging)

    # Create a base log file and a rotated file
    base_file = tmp_path / "drsearch_backend_log.jsonl"
    rotated_file = tmp_path / "drsearch_backend_log.jsonl.1"

    base_file.write_bytes(b'{"message":"line1"}\n')
    rotated_file.write_bytes(b'{"message":"old1"}\n{"message":"old2"}\n')

    # Fake storage capturing calls/content per blob path
    class FakeStorage:
        def __init__(self):
            self.appended = {}  # blob_path -> bytes
            self.created = set()
            self.lengths = {}  # blob_path -> int

        async def close(self):
            return

        async def ensure_append_blob(self, container_name, blob_name, content_type=None):
            # simulate creation
            self.created.add((container_name, blob_name))
            self.appended.setdefault(blob_name, b"")
            self.lengths.setdefault(blob_name, 0)

        async def get_blob_length(self, container_name, blob_name):
            return self.lengths.get(blob_name, 0)

        async def append_blob_bytes(self, container_name, blob_name, data: bytes):
            self.appended.setdefault(blob_name, b"")
            self.appended[blob_name] += data
            self.lengths[blob_name] = len(self.appended[blob_name])

    storage = FakeStorage()
    settings = LoggingSettings()

    # Act: one append pass (should upload current contents)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(core_pkg.logging._append_logs_once(settings, storage))

    # Append new data to base file and run again
    with base_file.open("ab") as fh:
        fh.write(b'{"message":"line2"}\n')

    loop.run_until_complete(core_pkg.logging._append_logs_once(settings, storage))

    # Assert: find blob keys used
    # We don't assert the date segment; focus on instance partition and filenames.
    # Expected subpath segment:
    # logs/dev/<YYYY-MM-DD>/backend/inst-123/<filename>
    instance_segment = "/backend/inst-123/"

    base_blob_paths = [p for p in storage.appended.keys() if p.endswith("drsearch_backend_log.jsonl")]
    rotated_blob_paths = [p for p in storage.appended.keys() if p.endswith("drsearch_backend_log.jsonl.1")]

    assert base_blob_paths, "Base log blob should be created and appended"
    assert rotated_blob_paths, "Rotated log blob should be included"

    for p in base_blob_paths + rotated_blob_paths:
        assert instance_segment in p, f"Blob path missing instance partition: {p}"
        assert p.startswith("logs/dev/"), f"Blob path should include NODE_ENV 'dev': {p}"

    # Validate content: base file should contain line1 then line2 (two appends)
    base_blob = storage.appended[base_blob_paths[0]]
    assert b'{"message":"line1"}\n' in base_blob
    assert base_blob.endswith(b'{"message":"line2"}\n')

    # Rotated file should contain both old lines from first pass
    rotated_blob = storage.appended[rotated_blob_paths[0]]
    assert rotated_blob == b'{"message":"old1"}\n{"message":"old2"}\n'

    # Now simulate a "restart": new FakeStorage with pre-existing remote length
    storage2 = FakeStorage()
    # Seed remote length for base blob as the current size, to ensure no duplicates appended on "restart"
    existing_len = len(base_blob)
    for p, content in storage.appended.items():
        storage2.appended[p] = content
        storage2.lengths[p] = len(content)

    # Write more to base file post-restart
    with base_file.open("ab") as fh:
        fh.write(b'{"message":"line3"}\n')

    loop.run_until_complete(core_pkg.logging._append_logs_once(settings, storage2))

    # Ensure only the new tail (line3) was appended after "restart"
    new_base_blob = storage2.appended[base_blob_paths[0]]
    assert new_base_blob.endswith(b'{"message":"line3"}\n')
    assert len(new_base_blob) == existing_len + len(b'{"message":"line3"}\n')
