# file: app/core/config.py

"""Centralised application configuration using *pydantic‑settings*."""

from functools import lru_cache
from typing import List, Optional


from pydantic import AnyHttpUrl, Field  # type: ignore
try:
    # Pydantic 2 style package (preferred)
    from pydantic_settings import BaseSettings  # type: ignore
except ImportError:  # pragma: no cover – fallback for environments without the extra package
    # Pydantic 1 exposes `BaseSettings` directly.  Importing from ``pydantic``
    # keeps the public type consistent for the rest of the module.
    from pydantic import BaseSettings  # type: ignore


# ---------------------------------------------------------------------------
# Optional Pydantic v2 features
# ---------------------------------------------------------------------------
# ``field_validator`` was introduced in Pydantic v2.  When running with an
# older (v1) version we create a **noop shim** so that the rest of the module
# can be imported without error during unit-tests.  The validation logic that
# depends on the decorator is *non-critical* for the test-suite so a noop is
# sufficient and avoids adding a hard dependency on Pydantic v2.

try:
    # Pydantic ≥ 2
    from pydantic import field_validator  # type: ignore
except ImportError:  # pragma: no cover – executed on Pydantic v1 only
    from pydantic import validator  # type: ignore  # Lazy import; v1 only

    def field_validator(field_name: str, *, mode: str = "before", **_unused):  # type: ignore
        """Simplified replacement using :func:`pydantic.validator` for v1."""

        pre = mode == "before"

        def _decorator(func):  # noqa: D401 – wraps the original validator
            return validator(field_name, pre=pre, allow_reuse=True)(func)

        return _decorator


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