from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    log_output_mode: str = Field("local", validation_alias="LOG_OUTPUT_MODE")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_file_max_mb: int = Field(20, validation_alias="LOG_FILE_MAX_MB")
    log_backup_count: int = Field(10, validation_alias="LOG_BACKUP_COUNT")
    log_to_blob_container: str = Field(
        "drsearch-logs", validation_alias="LOG_TO_BLOB_CONTAINER"
    )
    blob_upload_interval_sec: int = Field(
        300, validation_alias="BLOB_UPLOAD_INTERVAL_SEC"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )
