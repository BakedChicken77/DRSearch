# app\config.py
"""
Centralised configuration using Pydantic Settings.
Loads environment variables or .env file values at runtime.
"""
import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Core
    ENV: str = Field("development", env="ENV")
    # Postgres / pgvector
    PGVECTOR_URL: str = os.getenv("PGVECTOR_URL")
    PGVECTOR_INDEX: str = os.getenv("PGVECTOR_INDEX", "SEPS")
    PG_POOL_SIZE: int = 10
    # Agent

    AZURE_OPENAI_LLM_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_EMBEDDER: str = os.getenv("AZURE_OPENAI_EMBEDDER")    
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
