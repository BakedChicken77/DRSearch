from __future__ import annotations

from pydantic import BaseModel, Field


class LoggingSettings(BaseModel):
    """Configuration for application logging."""

    level: str = Field("INFO", env="LOG_LEVEL")
    file_max_mb: int = Field(20, env="LOG_FILE_MAX_MB")
    backup_count: int = Field(10, env="LOG_BACKUP_COUNT")
    log_format: str = Field("json", env="LOG_FORMAT")
    to_blob: bool = Field(False, env="LOG_TO_BLOB")
    blob_upload_interval_sec: int = Field(300, env="BLOB_UPLOAD_INTERVAL_SEC")
