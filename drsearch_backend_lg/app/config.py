from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/drsearch_lg"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # File upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    class Config:
        env_file = ".env"

def get_settings() -> Settings:
    return Settings()
