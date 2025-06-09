from pathlib import Path
from pydantic import BaseModel, Field


class LoggingSettings(BaseModel):
    """Structured logging configuration."""

    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file_max_mb: int = Field(20, env="LOG_FILE_MAX_MB")
    log_backup_count: int = Field(10, env="LOG_BACKUP_COUNT")
    log_format: str = Field("json", env="LOG_FORMAT")
    log_to_blob: bool = Field(False, env="LOG_TO_BLOB")
    blob_upload_interval_sec: int = Field(300, env="BLOB_UPLOAD_INTERVAL_SEC")

    # not exported via env
    log_dir: Path = Path("logs")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
