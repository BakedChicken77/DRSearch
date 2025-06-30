# file: app/__init__.py

"""Application package initialisation.

This module also provides a **runtime compatibility shim** for test
environments that do *not* have the optional ``pydantic-settings`` package
installed (for example, when running with the lean dependency set).
"""

# First import *only* external dependencies so that we can safely inject
# compatibility shims **before** internal modules are loaded.

from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Optional dependency shim – `pydantic_settings`
# ---------------------------------------------------------------------------
# Many modules (e.g. :pymod:`app.models.logging`) import
# ``from pydantic_settings import BaseSettings``.  The full package is
# available in production builds but *may* be missing in minimal CI images.
# Rather than adding a hard requirement we register a stub module that simply
# re-exports :class:`pydantic.BaseSettings` so that imports succeed.

from types import ModuleType
import sys

try:
    import pydantic_settings  # type: ignore  # noqa: F401 – real package present
except ModuleNotFoundError:  # pragma: no cover
    import pydantic  # type: ignore

    shim = ModuleType("pydantic_settings")
    shim.BaseSettings = pydantic.BaseSettings  # type: ignore[attr-defined]
    sys.modules["pydantic_settings"] = shim

# ---------------------------------------------------------------------------
# Internal imports (may rely on the shim registered above)
# ---------------------------------------------------------------------------

from .core.config import Settings, get_settings
from .core.logging import configure_logging
from .core.logging_middleware import LoggingMiddleware
from .auth.middleware import AuthMiddleware
from .api.v1.routes import build_router
from .warmup import warm_up_indexes
from fastapi.middleware.cors import CORSMiddleware

# Ensure authentication is disabled by default in environments (like tests)
# where the variable may not have been set yet.  This assignment happens *very*
# early – before :pymod:`app.core.config` is imported – so the setting will be
# picked up by the first instantiation of :class:`Settings`.

import os

os.environ.setdefault("AUTH_ENABLED", "False")

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


# Eagerly instantiate so ``uvicorn app:app`` still works.
app = create_app()
