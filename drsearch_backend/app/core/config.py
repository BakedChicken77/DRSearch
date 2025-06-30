# file: app/core/config.py

"""Centralised application configuration using *pydantic‑settings*."""

from functools import lru_cache
from typing import List, Optional


from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings


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

    tenant_id: Optional[str] = Field(None, env="AZURE_AD_TENANT_ID")
    client_id: Optional[str] = Field(None, env="AZURE_AD_CLIENT_ID")

    # ------------------------------------------------------------------
    # CORS / Front‑end
    # ------------------------------------------------------------------
    cors_origins: List[AnyHttpUrl] = Field(default_factory=lambda: ["http://localhost:3000"], env="CORS_ORIGINS")

    # ------------------------------------------------------------------
    # FastAPI metadata
    # ------------------------------------------------------------------
    api_title: str = "DRSearch API"
    api_version: str = "1.0.0"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf‑8",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra fields for testing
    }

    # ----------------- computed / validated -----------------
    @field_validator("auth_enabled", mode="before")
    @classmethod
    def _parse_auth_enabled(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if v is None:
            return ["http://localhost:3000"]  # Provide default
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance so settings are evaluated once only."""

    return Settings()