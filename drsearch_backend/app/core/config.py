# file: app/core/config.py

"""Centralised application configuration using *pydantic‑settings*."""

from functools import lru_cache
from typing import List


from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """DRSearch server configuration loaded from ``.env`` at runtime."""

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------
    debug: bool = Field(False, env="DEBUG")
    node_env: str = Field("production", env="NODE_ENV")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    auth_enabled: bool = Field(True, env="AUTH_ENABLED")
    whitelist: List[str] = Field(default_factory=list, env="WHITELIST")

    tenant_id: str = Field(..., env="AZURE_AD_TENANT_ID")
    client_id: str = Field(..., env="AZURE_AD_CLIENT_ID")

    # ------------------------------------------------------------------
    # CORS / Front‑end
    # ------------------------------------------------------------------
    cors_origins: List[AnyHttpUrl] = Field(..., env="CORS_ORIGINS")

    # ------------------------------------------------------------------
    # Azure Blob Storage
    # ------------------------------------------------------------------
    azure_blob_connection_string: str | None = Field(
        default=None, env="AZURE_BLOB_CONNECTION_STRING"
    )
    azure_blob_container: str | None = Field(default=None, env="AZURE_BLOB_CONTAINER")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file_max_mb: int = Field(20, env="LOG_FILE_MAX_MB")
    log_backup_count: int = Field(10, env="LOG_BACKUP_COUNT")
    log_format: str = Field("json", env="LOG_FORMAT")
    log_to_blob: bool = Field(False, env="LOG_TO_BLOB")
    blob_upload_interval_sec: int = Field(300, env="BLOB_UPLOAD_INTERVAL_SEC")

    # ------------------------------------------------------------------
    # FastAPI metadata
    # ------------------------------------------------------------------
    api_title: str = "DRSearch API"
    api_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf‑8"
        case_sensitive = True

    # ----------------- computed / validated -----------------
    @validator("cors_origins", pre=True)
    def _split_origins(cls, v: str | list[str]):  # noqa: N805 – pydantic API
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance so settings are evaluated once only."""

    return Settings()
