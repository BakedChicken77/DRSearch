from __future__ import annotations

import logging
import time
from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send


class LoggingMiddleware:
    """Middleware that logs HTTP requests and responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        start = time.time()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration = int((time.time() - start) * 1000)
        self.logger.info(
            "request",
            extra={
                "method": request.method,
                "path": scope.get("path"),
                "status": status,
                "client_ip": (scope.get("client") or ["", ""])[0],
                "user_agent": request.headers.get("user-agent", ""),
                "latency_ms": duration,
            },
        )
