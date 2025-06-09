import types
from pathlib import Path

import pytest

from app.core.blob_loader import download_startup_blobs
from app.models import BlobSettings


class DummyStorage:
    def __init__(self, *a, **k):
        self.downloads = []

    async def download_blob(self, container, blob, path):
        Path(path).write_text("dummy")
        self.downloads.append(blob)

    async def close(self):
        pass


def test_download_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.core.blob_loader.AzureBlobStorageAsync",
        DummyStorage,
    )
    settings = BlobSettings(connection_string="c", container="cont")
    # patch mapping to use tmp path
    from app.core import blob_loader

    monkeypatch.setattr(blob_loader, "_BLOB_MAP", {"file.txt": tmp_path / "f.txt"})
    download_startup_blobs(settings)
    assert (tmp_path / "f.txt").exists()


def test_missing_env(monkeypatch):
    settings = BlobSettings(connection_string=None, container=None)
    download_startup_blobs(settings)  # should not raise


def test_missing_blob(monkeypatch, tmp_path):
    class Failing(DummyStorage):
        async def download_blob(self, container, blob, path):
            raise Exception("not found")

    monkeypatch.setattr(
        "app.core.blob_loader.AzureBlobStorageAsync",
        Failing,
    )
    settings = BlobSettings(connection_string="c", container="cont")
    from app.core import blob_loader

    monkeypatch.setattr(blob_loader, "_BLOB_MAP", {"missing.txt": tmp_path / "m.txt"})
    download_startup_blobs(settings)  # should fall back without raising
    assert not (tmp_path / "m.txt").exists()
