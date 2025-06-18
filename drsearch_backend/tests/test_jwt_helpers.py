import types
import pytest
from app.auth.jwt import decode_bearer, TokenValidationError


def _patch_jwt(monkeypatch, ok=True):
    """Replace PyJWKClient & jwt.decode so no network / crypto is needed."""
    # -- PyJWKClient with dummy .get_signing_key_from_jwt ---------------------
    fake_key = types.SimpleNamespace(key="public-key")
    fake_client = types.SimpleNamespace(get_signing_key_from_jwt=lambda _t: fake_key)
    monkeypatch.setattr("app.auth.jwt.PyJWKClient", lambda *_a, **_kw: fake_client)

    # -- jwt.decode behaviour -------------------------------------------------
    if ok:

        def _dec(token, *_, **__):
            return {"sub": "user", "aud": "api://id", "iss": "issuer"}

    else:
        # def _dec(*_a, **_kw):
        #     raise Exception("bad token")  # noqa: BLE001
        import jwt  # keep inside helper

        def _dec(*_a, **_kw):
            raise jwt.InvalidTokenError("bad")

    monkeypatch.setattr("app.auth.jwt.jwt.decode", _dec)


def test_decode_bearer_success(monkeypatch):
    _patch_jwt(monkeypatch, ok=True)
    out = decode_bearer("tok", "api://id", "issuer", "jwks")
    assert out["sub"] == "user"


def test_decode_bearer_failure(monkeypatch):
    _patch_jwt(monkeypatch, ok=False)
    with pytest.raises(TokenValidationError):
        decode_bearer("tok", "api://id", "issuer", "jwks")
