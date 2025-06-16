"""
Connection helpers for PostgreSQL + pgvector.
Uses psycopg3 connection pool in 'async' mode.
"""

from contextlib import asynccontextmanager
import psycopg_pool
from .config import get_settings

settings = get_settings()

# Initialise a global async pool (lazy connection).
pool = psycopg_pool.AsyncConnectionPool(
    conninfo=(
        settings.PGVECTOR_URL
    ),
    open=False,
    max_size=settings.PG_POOL_SIZE,
)


async def open_pool_once() -> None:
    """Open the pool the first time the app starts."""
    if pool.closed:
        await pool.open()


@asynccontextmanager
async def get_conn():
    """Async context-manager yielding a live connection from the pool."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            yield cur
