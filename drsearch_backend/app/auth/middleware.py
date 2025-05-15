# file: app/auth/middleware.py

"""FastAPI middleware that enforces Azure AD JWT authentication."""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..core.config import Settings
from .jwt import TokenValidationError, decode_bearer

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """ASGI middleware that enforces Azure AD JWT authentication."""

    # paths to skip authentication even when auth_enabled=True
    WHITELIST = {
        "/chat/playground",
        "/favicon.ico",
        "/index-options",
    }

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

        # Pre-fetch OIDC metadata once
        if self.settings.auth_enabled:
            import requests

            oidc_url = (
                f"https://login.microsoftonline.us/"
                f"{self.settings.tenant_id}/.well-known/openid-configuration"
            )
            try:
                self._oidc_config = requests.get(oidc_url, timeout=5).json()
            except requests.RequestException as exc:
                logger.critical("Failed to fetch OIDC metadata", exc_info=exc)
                raise RuntimeError("Unable to start – OIDC discovery failed") from exc

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle HTTP requests; pass through websockets, lifespan, etc.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Bypass entirely in dev mode
        if not self.settings.auth_enabled:
            request.state.user = {"username": "devuser"}
            await self.app(scope, receive, send)
            return

        # Whitelist via env
        if scope["path"] in self.settings.whitelist:
            await self.app(scope, receive, send)
            return

        # Allow CORS preflight
        if request.method.upper() == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Extract Bearer token
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            resp = JSONResponse({"detail": "Missing bearer token"}, status_code=401)
            await resp(scope, receive, send)
            return

        token = auth.split(" ", 1)[1]

        # Validate
        try:
            decoded = decode_bearer(
                token=token,
                audience=f"api://{self.settings.client_id}",
                issuer=self._oidc_config["issuer"],
                jwks_uri=self._oidc_config["jwks_uri"],
            )
        except TokenValidationError as exc:
            resp = JSONResponse({"detail": str(exc)}, status_code=401)
            await resp(scope, receive, send)
            return

        # Attach user and continue
        request.state.user = decoded
        await self.app(scope, receive, send)
