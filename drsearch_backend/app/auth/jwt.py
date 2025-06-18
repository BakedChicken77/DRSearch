# file: app/auth/jwt.py

"""JWT token verification helpers (Azure AD)."""

from __future__ import annotations

import logging
from functools import cache
from typing import Any, Dict

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class TokenValidationError(RuntimeError):
    """Raised when an incoming JWT cannot be validated."""


@cache
def _jwks_client(jwks_uri: str) -> PyJWKClient:  # pragma: no cover
    return PyJWKClient(jwks_uri)


def decode_bearer(
    token: str, audience: str, issuer: str, jwks_uri: str
) -> Dict[str, Any]:
    """Validate *token* and return decoded claims.

    Args:
        token: Raw ``Bearer …`` string without the prefix.
        audience: Expected *aud* claim (API Application ID URI).
        issuer:  Expected *iss* claim (Azure AD tenant issuer).
        jwks_uri: JWKS endpoint for the tenant.

    Raises:
        TokenValidationError: On expiry or signature / claim mismatch.

    Returns:
        Decoded JWT claims as dictionary.
    """

    client = _jwks_client(jwks_uri)
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],  # RS256
            audience=audience,
            issuer=issuer,
            options={"verify_aud": True, "verify_iss": True},
        )
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover
        logger.info("JWT expired", exc_info=exc)
        raise TokenValidationError("Token expired") from exc
    except jwt.InvalidTokenError as exc:  # pragma: no cover
        logger.info("Invalid JWT", exc_info=exc)
        raise TokenValidationError(str(exc)) from exc
