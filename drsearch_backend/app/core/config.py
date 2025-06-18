# file: app/core/config.py

"""Centralised application configuration using *pydantic‑settings*."""

from functools import lru_cache
from typing import List


from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DRSearch server configuration loaded from ``.env`` at runtime."""

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------
    debug: bool = Field(False, validation_alias="DEBUG")
    node_env: str = Field("production", validation_alias="NODE_ENV")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    auth_enabled: bool = Field(True, validation_alias="AUTH_ENABLED")
    whitelist: List[str] = Field(default_factory=list, validation_alias="WHITELIST")

    tenant_id: str = Field(..., validation_alias="AZURE_AD_TENANT_ID")
    client_id: str = Field(..., validation_alias="AZURE_AD_CLIENT_ID")

    # ------------------------------------------------------------------
    # CORS / Front‑end
    # ------------------------------------------------------------------
    cors_origins: List[AnyHttpUrl] = Field(..., validation_alias="CORS_ORIGINS")

    # ------------------------------------------------------------------
    # FastAPI metadata
    # ------------------------------------------------------------------
    api_title: str = "DRSearch API"
    api_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Prioritize init settings over environment for test overrides."""
        return env_settings, dotenv_settings, file_secret_settings, init_settings

    # ----------------- computed / validated -----------------
    @field_validator("cors_origins", mode="before")
    def _split_origins(cls, v: str | list[str]):  # noqa: N805 – pydantic API
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance so settings are evaluated once only."""

    return Settings()
