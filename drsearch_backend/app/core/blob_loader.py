from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

try:  # Optional dependency in test environments
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except Exception:  # pragma: no cover - azure not installed
    BlobServiceClient = None  # type: ignore

    class ResourceNotFoundError(Exception):
        pass


from app.models import BlobSettings

logger = logging.getLogger(__name__)


_DEFAULT_MAPPINGS = {
    "System_Prompts.py": Path(__file__).resolve().parent.parent / "System_Prompts.py",
    "index_config.py": Path(__file__).resolve().parent.parent / "index_config.py",
    "index_options.py": Path(__file__).resolve().parent.parent / "index_options.py",
    "reference_docs_mappings/JACSKE_PROD_DEPLOY.csv": Path(__file__)
    .resolve()
    .parent.parent
    / "reference_docs_mappings"
    / "JACSKE_PROD_DEPLOY.csv",
}


def _env_settings() -> Optional[BlobSettings]:
    """Return BlobSettings from environment or ``None`` when incomplete."""
    conn = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    container = os.getenv("AZURE_BLOB_CONTAINER")
    if conn and container:
        return BlobSettings(connection_string=conn, container=container)
    return None


def download_config_files(
    settings: BlobSettings, mappings: Dict[str, Path] | None = None
) -> None:
    """Download required config files from Azure Blob Storage."""
    mappings = mappings or _DEFAULT_MAPPINGS
    if BlobServiceClient is None:
        logger.warning("azure-storage-blob not installed; skipping download")
        return
    try:
        client = BlobServiceClient.from_connection_string(settings.connection_string)
    except Exception as exc:  # pragma: no cover - catastrophic
        logger.warning("Blob storage unavailable: %s", exc)
        return

    for blob_name, local_path in mappings.items():
        try:
            blob_client = client.get_blob_client(
                container=settings.container, blob=blob_name
            )
            data = blob_client.download_blob().readall()
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            logger.info("Downloaded blob '%s'", blob_name)
        except ResourceNotFoundError:
            logger.warning("Blob '%s' not found", blob_name)
        except Exception as exc:  # pragma: no cover - network related
            logger.warning("Failed to download '%s': %s", blob_name, exc)


def fetch_startup_blobs() -> None:
    """Fetch config blobs if environment variables are configured."""
    settings = _env_settings()
    if not settings:
        logger.info("Blob storage not configured; using local files")
        return
    download_config_files(settings)
