# file: app/__init__.py

"""Application package initialisation."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import Settings, get_settings
from .core.logging import configure_logging
from .core.logging_middleware import LoggingMiddleware
from .auth.middleware import AuthMiddleware
from .api.v1.routes import build_router
from .warmup import warm_up_indexes


def create_app() -> FastAPI:
    """Factory responsible for building the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI instance ready to be run by Uvicorn.
    """

    settings: Settings = get_settings()
    configure_logging()

    # -------------------- lifespan --------------------
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await warm_up_indexes()
        yield

    app = FastAPI(debug=settings.debug, lifespan=lifespan)

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

    # -------------------- openapi fix --------------------
    from fastapi.openapi.utils import get_openapi
    from pydantic.errors import PydanticUserError
    from pydantic import BaseModel

    # LangServe is optional – the backend no longer depends on it, but the
    # OpenAPI fallback originally relied on `langserve.validation` classes.  We
    # attempt an import and gracefully continue if LangServe is not present so
    # the application can run without the package installed.

    try:
        import langserve.validation as lv  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        lv = None  # type: ignore

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        try:
            app.openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
        except PydanticUserError:
            # When LangServe is installed we rebuild its models to satisfy
            # Pydantic.  If it is not available we can safely skip this step.
            if lv is not None:
                for obj in lv.__dict__.values():
                    if isinstance(obj, type) and issubclass(obj, BaseModel):
                        try:
                            obj.model_rebuild(force=True)
                        except AttributeError:  # pragma: no cover – defensive
                            pass
            app.openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


# Application instance for `uvicorn app:app` style invocation.
# By default the application is fully initialised.  Tests can set
# ``INIT_APP=false`` to defer creation until explicitly requested.
if os.getenv("INIT_APP", "true").lower() == "true":
    app = create_app()
else:
    app = FastAPI()
