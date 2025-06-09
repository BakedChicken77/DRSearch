# file: app/__init__.py

"""Application package initialisation."""

from fastapi import FastAPI

from .core.config import Settings, get_settings
from .core.logging import configure_logging
from .core.logging_middleware import LoggingMiddleware
from .core.blob_loader import download_startup_blobs
from .models import BlobSettings, LoggingSettings
from .auth.middleware import AuthMiddleware
from .api.v1.routes import build_router
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Factory responsible for building the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI instance ready to be run by Uvicorn.
    """

    settings: Settings = get_settings()
    blob_settings = BlobSettings()
    logging_settings = LoggingSettings()

    # Download configuration files before app creation
    download_startup_blobs(blob_settings)

    configure_logging(logging_settings, blob_settings)

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
    app.add_middleware(AuthMiddleware, settings=settings)
    app.add_middleware(LoggingMiddleware)

    # -------------------- routers --------------------
    app.include_router(build_router(settings=settings))

    return app


# Eagerly instantiate so ``uvicorn app:app`` still works.
app = create_app()
