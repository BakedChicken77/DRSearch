"""
Centralised configuration using Pydantic Settings.
Loads environment variables or .env file values at runtime.
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Core
    ENV: str = Field("development", env="ENV")
    OPENAI_API_KEY: str
    # Postgres / pgvector
    PG_HOST: str = "db"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = "postgres"
    PG_DATABASE: str = "drsearch"
    PG_POOL_SIZE: int = 10
    # Agent
    OPENAI_MODEL: str = "gpt-4o"
    AGENT_TEMPERATURE: float = 0.0
    MAX_TOKENS: int = 1024
    # Runtime
    LOG_LEVEL: str = "INFO"
    DATA_DIR: Path = Path("/data")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:  # noqa: D401
    """Return cached Settings singleton."""
    return Settings()
