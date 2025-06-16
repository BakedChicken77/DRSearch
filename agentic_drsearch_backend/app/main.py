"""
FastAPI application factory. Uvicorn launches this module:app
"""

from fastapi import FastAPI
from .config import get_settings
from .database import open_pool_once
from .api.v1.routes import router as v1_router
from .logging import logger
import sys
import asyncio
# Use system trust store for SSL certificate verification.
# This ensures that Python honors certificates trusted by Windows (e.g., Microsoft RSA TLS CA 02),
# which may be missing from certifi's default bundle. Required for Azure US Gov endpoints.
import truststore
truststore.inject_into_ssl()    


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



settings = get_settings()

app = FastAPI(
    title="Agentic DR-Search Backend",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "production" else None,
)

# Register routes
app.include_router(v1_router)


@app.on_event("startup")
async def startup_event():
    """Initialise database pool and log environment."""
    await open_pool_once()
    logger.info("🚀 Backend started in %s mode", settings.ENV)
