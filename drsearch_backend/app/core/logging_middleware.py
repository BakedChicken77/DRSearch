from time import monotonic
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("http")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = monotonic()
        response = await call_next(request)
        latency = monotonic() - start
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency": latency,
                "client_ip": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        return response
