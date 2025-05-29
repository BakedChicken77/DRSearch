from __future__ import annotations

from pydantic import BaseModel, Field


class BlobSettings(BaseModel):
    """Configuration for Azure Blob Storage."""

    connection_string: str = Field(..., env="AZURE_BLOB_CONNECTION_STRING")
    container: str = Field(..., env="AZURE_BLOB_CONTAINER")
