from pydantic import BaseModel, Field


class BlobSettings(BaseModel):
    """Configuration required to access Azure Blob Storage."""

    connection_string: str | None = Field(None, env="AZURE_BLOB_CONNECTION_STRING")
    container: str | None = Field(None, env="AZURE_BLOB_CONTAINER")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
