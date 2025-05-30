# file: app/__init__.py

"""Application package initialisation."""

from fastapi import FastAPI

from .core.logging import configure_logging
from .models import LoggingSettings, BlobSettings
from .core.blob_loader import fetch_startup_blobs
from .core.logging_middleware import LoggingMiddleware

fetch_startup_blobs()

from .core.config import Settings, get_settings
from .auth.middleware import AuthMiddleware
from .api.v1.routes import build_router
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Factory responsible for building the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI instance ready to be run by Uvicorn.
    """

    settings: Settings = get_settings()
    configure_logging(
        settings=LoggingSettings(
            level=settings.log_level,
            file_max_mb=settings.log_file_max_mb,
            backup_count=settings.log_backup_count,
            log_format=settings.log_format,
            to_blob=settings.log_to_blob,
            blob_upload_interval_sec=settings.blob_upload_interval_sec,
        ),
        blob=BlobSettings(
            connection_string=settings.azure_blob_connection_string,
            container=settings.azure_blob_container,
        )
        if settings.azure_blob_connection_string and settings.azure_blob_container
        else None,
    )

    app = FastAPI(debug=settings.debug)

    # ------------------- ADD CORS -------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------- middleware -------------------
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuthMiddleware, settings=settings)

    # -------------------- routers --------------------
    app.include_router(build_router(settings=settings))

    return app


# Eagerly instantiate so ``uvicorn app:app`` still works.
app = create_app()
