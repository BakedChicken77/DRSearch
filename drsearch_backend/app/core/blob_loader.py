from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.models import BlobSettings

try:  # optional external wrapper
    from azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
        AzureBlobStorageAsync,
    )
except Exception:  # pragma: no cover - fallback
    from azure.storage.blob.aio import BlobServiceClient

    class AzureBlobStorageAsync:  # type: ignore
        def __init__(self, connection_string: str):
            self._client = BlobServiceClient.from_connection_string(connection_string)

        async def download_blob(self, container: str, blob: str, path: str) -> None:
            blob_client = self._client.get_blob_client(container, blob)
            data = await blob_client.download_blob()
            with open(path, "wb") as f:
                f.write(await data.readall())

        async def upload_blob(self, container: str, blob: str, path: str) -> None:
            blob_client = self._client.get_blob_client(container, blob)
            with open(path, "rb") as f:
                await blob_client.upload_blob(f, overwrite=True)

        async def close(self) -> None:
            await self._client.close()


logger = logging.getLogger(__name__)

# Mapping of blob name -> local absolute path
_BLOB_MAP = {
    "JACSKE_PROD_DEPLOY.csv": Path(__file__).resolve().parent.parent
    / "reference_docs_mappings"
    / "JACSKE_PROD_DEPLOY.csv",
    "System_Prompts.py": Path(__file__).resolve().parent.parent / "System_Prompts.py",
    "index_config.py": Path(__file__).resolve().parent.parent / "index_config.py",
    "index_options.py": Path(__file__).resolve().parent.parent / "index_options.py",
}


async def _download(settings: BlobSettings) -> None:
    storage = AzureBlobStorageAsync(settings.connection_string)
    for blob, path in _BLOB_MAP.items():
        try:
            await storage.download_blob(settings.container, blob, str(path))
            logger.info("Downloaded %s", blob)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Using local copy for %s: %s", blob, exc)
    await storage.close()


def download_startup_blobs(settings: BlobSettings) -> None:
    """Synchronously download blobs if configuration present."""
    if not settings.connection_string or not settings.container:
        logger.info("Blob settings missing; skipping downloads")
        return
    asyncio.run(_download(settings))
