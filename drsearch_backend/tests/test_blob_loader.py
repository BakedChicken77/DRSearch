import builtins
from pathlib import Path

import pytest

from app.core import blob_loader
from app.models import BlobSettings


class DummyBlob:
    def __init__(self, name: str):
        self.name = name

    def download_blob(self):
        class Stream:
            def readall(self_inner):
                return f"data-{self.name}".encode()

        return Stream()


class DummyClient:
    def __init__(self):
        self.requested = []

    def get_blob_client(self, container: str, blob: str):
        self.requested.append((container, blob))
        return DummyBlob(blob)


def test_download_config_files_success(tmp_path, monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(
        blob_loader,
        "BlobServiceClient",
        type("x", (), {"from_connection_string": lambda *_: client}),
    )

    settings = BlobSettings(connection_string="c", container="cont")
    mapping = {"file.txt": tmp_path / "file.txt"}
    blob_loader.download_config_files(settings, mapping)

    assert mapping["file.txt"].read_text() == "data-file.txt"
    assert client.requested == [("cont", "file.txt")]


def test_fetch_startup_blobs_no_env(monkeypatch):
    monkeypatch.delenv("AZURE_BLOB_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_BLOB_CONTAINER", raising=False)
    # Should not raise
    blob_loader.fetch_startup_blobs()
