from __future__ import annotations

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_name: str = "drsearch.request"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000
        self.logger.info(
            "HTTP request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round(duration, 2),
                "client": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        return response
