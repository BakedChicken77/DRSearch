# file: app/main.py

"""Uvicorn entry‑point – minimal & testable (no global state)."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import suppress
from typing import Callable

import uvicorn

from . import create_app
from .core.config import get_settings

logger = logging.getLogger(__name__)


async def _shutdown(loop: asyncio.AbstractEventLoop) -> None:  # pragma: no cover
    tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
    for task in tasks:
        task.cancel()
    with suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks)


def main() -> None:
    """CLI that mirrors legacy *python main.py* behaviour."""

    settings = get_settings()
    app = create_app()

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8010, reload=settings.debug)
    server = uvicorn.Server(config=config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(_shutdown(loop)))

    logger.info(
        "Starting DRSearch API", extra={"port": 8010, "auth": settings.auth_enabled}
    )
    loop.run_until_complete(server.serve())


if __name__ == "__main__":
    main()
