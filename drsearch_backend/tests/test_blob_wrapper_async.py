import asyncio  # noqa: F401 – required for @pytest.mark.asyncio runtime
import base64
import types
from pathlib import Path
import os
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError  # type: ignore

import pytest  # type: ignore

from app.azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
    AzureBlobStorageAsync,
    Element,
    ElementMetadata,
)


class _DummyAsyncIter:
    """Minimal async iterator wrapper for deterministic lists."""

    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeBlobClient:
    """Pretends to be an Azure *BlobClient* – enough for our wrapper."""

    def __init__(self, raise_error: bool = False):
        self._raise = raise_error
        self.uploaded = None
        self.deleted = False

    async def upload_blob(self, data, overwrite=True):  # noqa: D401
        if self._raise:
            from azure.core.exceptions import ResourceNotFoundError

            raise ResourceNotFoundError("upload failed")
        # Capture data for assertion when provided as *bytes* (unit-tests only).
        if isinstance(data, (bytes, bytearray)):
            self.uploaded = bytes(data)
        else:  # opened file object
            self.uploaded = data.read()

    async def download_blob(self):
        if self._raise:
            from azure.core.exceptions import ResourceNotFoundError

            raise ResourceNotFoundError("download failed")

        class _Stream:
            async def readall(self):  # noqa: D401
                return b"dummy-data"

        return _Stream()

    async def delete_blob(self, *_, **__):
        self.deleted = True
        if self._raise:
            from azure.core.exceptions import HttpResponseError

            raise HttpResponseError("delete failed")

    async def create_snapshot(self):
        if self._raise:
            from azure.core.exceptions import HttpResponseError

            raise HttpResponseError("snap failed")
        return {"snapshot": "snappy"}

    async def start_copy_from_url(self, *_):
        return None

    async def abort_copy(self, *_):
        return None

    async def acquire_lease(self):
        return "lease-id"

    async def undelete_blob(self):
        return None

    async def get_blob_properties(self):
        # Return object with .copy fields to simulate pending copy.
        return types.SimpleNamespace(copy=types.SimpleNamespace(status="pending", id="copy-id"))


class _FakeContainerClient:
    async def create_container(self):
        return None

    async def delete_container(self, *_, **__):
        return None

    async def set_container_metadata(self, *, metadata):
        self.metadata = metadata

    async def get_container_properties(self):
        return types.SimpleNamespace(metadata={"foo": "bar"})

    def list_blobs(self):
        return _DummyAsyncIter([types.SimpleNamespace(name="blobA")])

    async def acquire_lease(self):
        return "lease-container"


class _FakeBlobService:
    """Stub for *BlobServiceClient* covering every call path used by wrapper."""

    def __init__(self):
        self._client_success = _FakeBlobClient()
        self._client_fail = _FakeBlobClient(raise_error=True)
        self.containers_deleted: list[str] = []

    @classmethod
    def from_connection_string(cls, *_):
        return cls()

    def get_blob_client(self, *, blob: str, **__):  # noqa: D401
        # Any blob name containing the substring "fail" triggers the error path.
        return self._client_fail if "fail" in blob else self._client_success

    def get_container_client(self, *_):
        return _FakeContainerClient()

    async def set_service_properties(self, *_, **__):
        return None

    async def get_service_properties(self):
        return {}

    async def get_service_stats(self):
        return {}

    def list_containers(self, name_starts_with: str | None = None):
        items = [types.SimpleNamespace(name="abc"), types.SimpleNamespace(name="testprefix_1")]
        if name_starts_with:
            items = [i for i in items if i.name.startswith(name_starts_with)]
        return _DummyAsyncIter(items)

    async def close(self):
        return None


# Note: we execute the coroutine test body via ``asyncio.run`` to avoid
# requiring the *pytest-asyncio* plugin (keeping dependencies minimal).


def test_blob_wrapper_happy_and_error_paths(monkeypatch, tmp_path):
    """Exercise *most* lines in AzureBlobStorageAsync including error branches."""

    # Patch the SDK client inside the wrapper module **before** instantiation.
    monkeypatch.setattr(
        "app.azure_search_blob_manager.AzureBlobStorageWrapperAsync.BlobServiceClient",
        _FakeBlobService,
    )

    async def _test():
        wrapper = AzureBlobStorageAsync("AccountName=dummy;EndpointSuffix=core.windows.net")

        # ---- simple helpers ---------------------------------------------------
        assert wrapper.get_value_from_connection_string("AccountName") == "dummy"
        assert wrapper.get_value_from_connection_string("EndpointSuffix") == "core.windows.net"

        # ---- blob upload from base64 (success) --------------------------------
        content_b64 = base64.b64encode(b"hello world").decode()
        await wrapper.upload_blob_from_base64("c1", "blob-ok", content_b64)

        # The fake client captured the raw bytes.
        assert wrapper.blob_service_client._client_success.uploaded == b"hello world"

        # ---- blob upload that triggers *except* branch ------------------------
        await wrapper.upload_blob_from_base64("c1", "blob-fail", content_b64)

        # ---- bytes upload convenience helper ----------------------------------
        await wrapper.upload_blob_bytes("c1", "blob-bytes", b"DATA")

        # ---- round-trip base64 download (uses *download_blob*) -----------------
        downloaded_b64 = await wrapper.download_blob_as_base64("c1", "blob-ok")
        assert base64.b64decode(downloaded_b64) == b"dummy-data"

        # ---- text download helper ---------------------------------------------
        text = await wrapper.download_blob_text("c1", "blob-ok")
        assert text == "dummy-data"

        # ---- container metadata helpers ---------------------------------------
        await wrapper.set_container_metadata("c1", {"k": "v"})
        md = await wrapper.get_container_metadata("c1")
        assert md == {"foo": "bar"}

        # ---- call remaining branchy helpers (errors swallowed) ----------------
        await wrapper.create_container("c1")
        await wrapper.delete_container("c1")

        await wrapper.create_blob_snapshot("c1", "blob-ok")
        await wrapper.create_blob_snapshot("c1", "blob-fail")

        await wrapper.soft_delete_and_undelete_blob("c1", "blob-ok")

        await wrapper.start_and_abort_blob_copy("https://example.com/src", "c1", "blob-ok")

        await wrapper.acquire_and_manage_leases("c1")  # container lease
        await wrapper.acquire_and_manage_leases("c1", "blob-ok")  # blob lease

        await wrapper.get_blob_service_properties_and_stats()

        # list & delete containers (verification skipped)
        await wrapper.list_all_containers()
        await wrapper.delete_all_containers(skip_verification=True)

        await wrapper.delete_containers_with_prefix("testprefix")

        # ---- export images to HTML --------------------------------------------
        img_elements = [
            Element(metadata=ElementMetadata(images=["i1.png", "i2.png", "i1.png"]))
        ]

        # Patch *download_blob* so we avoid nested SDK calls and actually create the file.
        async def _fake_download_blob(container, blob_name, download_path):  # noqa: D401
            Path(download_path).write_bytes(b"bin")

        monkeypatch.setattr(wrapper, "download_blob", _fake_download_blob)

        html_path = await wrapper.export_elements_images_to_html(
            img_elements,
            container_name="c1",
            output_dir=tmp_path,
            html_filename="gallery.html",
            max_images=0,
        )
        assert html_path.exists()
        contents = html_path.read_text()
        # Two unique images => two <img> tags expected.
        assert contents.count("<img") == 2

        await wrapper.close()

    # Run the coroutine test body
    asyncio.run(_test())

    # Restore a fresh event loop for subsequent tests that require it.
    asyncio.set_event_loop(asyncio.new_event_loop())


def test_upload_and_download_blob(monkeypatch, tmp_path):
    """Cover *upload_blob* and *download_blob* helpers."""

    # Patch BlobServiceClient as earlier
    monkeypatch.setattr(
        "app.azure_search_blob_manager.AzureBlobStorageWrapperAsync.BlobServiceClient",
        _FakeBlobService,
    )
    wrapper = AzureBlobStorageAsync("AccountName=dummy;EndpointSuffix=x")

    # ---- upload via file path --------------------------------------------
    src = tmp_path / "file.txt"
    src.write_text("content")
    asyncio.run(wrapper.upload_blob("c1", "blob-file", str(src)))
    assert wrapper.blob_service_client._client_success.uploaded == b"content"

    # ---- download into path ----------------------------------------------
    dst = tmp_path / "out.txt"
    asyncio.run(wrapper.download_blob("c1", "blob-file", str(dst)))
    assert dst.read_bytes() == b"dummy-data"


def test_export_images_error_branches(monkeypatch, tmp_path):
    """Trigger ResourceNotFound and HttpResponseError branches during export."""

    monkeypatch.setattr(
        "app.azure_search_blob_manager.AzureBlobStorageWrapperAsync.BlobServiceClient",
        _FakeBlobService,
    )
    wrapper = AzureBlobStorageAsync("AccountName=dummy;EndpointSuffix=x")

    # Prepare elements referencing two images – one OK, one raises errors
    elements = [
        Element(metadata=ElementMetadata(images=["ok.png", "missing.png", "error.png"]))
    ]

    # Custom download_blob that raises for certain names
    async def _dl(container, name, path):  # noqa: D401
        if name == "missing.png":
            raise ResourceNotFoundError("msg")
        if name == "error.png":
            raise HttpResponseError("boom")
        Path(path).write_bytes(b"img")

    monkeypatch.setattr(wrapper, "download_blob", _dl)

    # Use max_images=2 to exercise slice branch
    html = asyncio.run(
        wrapper.export_elements_images_to_html(
            elements,
            container_name="c1",
            output_dir=tmp_path,
            html_filename="gal.html",
            max_images=2,
        )
    )
    assert html.exists()
    body = html.read_text()
    # Only images that downloaded successfully ('ok.png') are embedded
    assert body.count("<img") == 1