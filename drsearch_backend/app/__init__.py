# file: app/__init__.py

"""Application package initialisation."""

import os
from fastapi import FastAPI

from .core.config import Settings, get_settings
from .core.logging import configure_logging
from .core.logging_middleware import LoggingMiddleware
from .auth.middleware import AuthMiddleware
from .api.v1.routes import build_router
from .warmup import warm_up_indexes
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Factory responsible for building the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI instance ready to be run by Uvicorn.
    """

    settings: Settings = get_settings()
    configure_logging()

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

    @app.on_event("startup")
    async def warm_up() -> None:
        await warm_up_indexes()

    return app


# Application instance for `uvicorn app:app` style invocation. Set the
# environment variable ``INIT_APP=false`` during tests to defer creation
# until explicitly requested.
if os.getenv("INIT_APP", "false").lower() == "true":
    app = create_app()
else:
    app = FastAPI()
