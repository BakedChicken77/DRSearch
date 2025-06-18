from pydantic import Field
from pydantic_settings import BaseSettings


class LoggingSettings(BaseSettings):
    log_output_mode: str = Field("local", env="LOG_OUTPUT_MODE")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file_max_mb: int = Field(20, env="LOG_FILE_MAX_MB")
    log_backup_count: int = Field(10, env="LOG_BACKUP_COUNT")
    log_to_blob_container: str = Field("drsearch-logs", env="LOG_TO_BLOB_CONTAINER")
    blob_upload_interval_sec: int = Field(300, env="BLOB_UPLOAD_INTERVAL_SEC")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
