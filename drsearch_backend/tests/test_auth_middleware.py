from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.requests import Request
import requests
import types
import pytest
from app.auth.jwt import TokenValidationError


from app.auth.middleware import AuthMiddleware


def _base_app():  # returns 200 /json
    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    # return Starlette(routes=[]).add_middleware(AuthMiddleware, settings=types.SimpleNamespace(
    #     auth_enabled=False, whitelist=set()
    # )), endpoint  # noqa: E501
    app = Starlette()
    app.add_middleware(AuthMiddleware, settings=types.SimpleNamespace(
        auth_enabled=False, whitelist=set()
    ))
    return app, endpoint


def test_middleware_pass_through_when_disabled():
    app, endpoint = _base_app()
    app.add_route("/", endpoint, methods=["GET"])
    client = TestClient(app)
    assert client.get("/").status_code == 200


def test_middleware_unauthenticated(monkeypatch):
    # ── 1. stub out token-decoder so we never verify real JWTs ───────────────
    monkeypatch.setattr("app.auth.middleware.decode_bearer",
                        lambda *_a, **_kw: {})

    # ── 2. stub the OIDC metadata HTTP call that AuthMiddleware makes ───────
    monkeypatch.setattr(
        "requests.get",
        lambda *_a, **_kw: types.SimpleNamespace(
            json=lambda: {"issuer": "i", "jwks_uri": "u"}
        ),
    )

    # (Alternative: if you prefer to keep the attribute on the class instead)
    # monkeypatch.setattr(
    #     AuthMiddleware, "_oidc_config",
    #     {"issuer": "i", "jwks_uri": "u"}, raising=False
    # )

    # ── 3. build an app with auth *enabled* ─────────────────────────────────
    settings = types.SimpleNamespace(
        auth_enabled=True,
        whitelist=set(),
        tenant_id="t",
        client_id="c",
    )

    app = Starlette()
    app.add_middleware(AuthMiddleware, settings=settings)

    @app.route("/")
    async def root(_):
        return JSONResponse({"hi": 1})

    # ── 4. exercise the middleware branches ────────────────────────────────
    with TestClient(app) as c:
        assert c.get("/").status_code == 401           # no token
        assert c.get("/", headers={"Authorization": "Bearer abc"}).status_code == 200


def test_oidc_fetch_fails(monkeypatch):
    def raise_error(*_a, **_kw):
        raise requests.RequestException("OIDC BOOM")  # ✅ Correct type

    monkeypatch.setattr("requests.get", raise_error)

    settings = types.SimpleNamespace(
        auth_enabled=True,
        whitelist=set(),
        tenant_id="dummy",
        client_id="client"
    )

    with pytest.raises(RuntimeError, match="Unable to start"):
        AuthMiddleware(app=lambda *_: None, settings=settings)

def test_whitelisted_path(monkeypatch):
    monkeypatch.setattr("app.auth.middleware.decode_bearer", lambda *_a, **_kw: {})
    monkeypatch.setattr("requests.get", lambda *_a, **_kw: types.SimpleNamespace(json=lambda: {"issuer": "i", "jwks_uri": "u"}))

    settings = types.SimpleNamespace(
        auth_enabled=True,
        whitelist={"/test-whitelist"},
        tenant_id="dummy",
        client_id="client"
    )

    app = Starlette()

    @app.route("/test-whitelist")
    async def handler(_):
        return JSONResponse({"whitelisted": True})

    app.add_middleware(AuthMiddleware, settings=settings)

    client = TestClient(app)
    r = client.get("/test-whitelist")
    assert r.status_code == 200
    assert r.json()["whitelisted"] is True

def test_options_method_skips_auth(monkeypatch):
    monkeypatch.setattr("app.auth.middleware.decode_bearer", lambda *_a, **_kw: {})
    monkeypatch.setattr("requests.get", lambda *_a, **_kw: types.SimpleNamespace(json=lambda: {"issuer": "i", "jwks_uri": "u"}))

    settings = types.SimpleNamespace(
        auth_enabled=True,
        whitelist=set(),
        tenant_id="dummy",
        client_id="client"
    )

    app = Starlette()

    @app.route("/test-options", methods=["OPTIONS", "GET"])
    async def handler(_):
        return JSONResponse({"ok": True})

    app.add_middleware(AuthMiddleware, settings=settings)

    client = TestClient(app)
    r = client.options("/test-options")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_invalid_token_rejected(monkeypatch):
    def raise_invalid_token(*_a, **_kw):
        raise TokenValidationError("bad signature")

    monkeypatch.setattr("app.auth.middleware.decode_bearer", raise_invalid_token)
    monkeypatch.setattr("requests.get", lambda *_a, **_kw: types.SimpleNamespace(json=lambda: {"issuer": "i", "jwks_uri": "u"}))

    settings = types.SimpleNamespace(
        auth_enabled=True,
        whitelist=set(),
        tenant_id="dummy",
        client_id="client"
    )

    app = Starlette()

    @app.route("/secure")
    async def handler(_):
        return JSONResponse({"secure": True})

    app.add_middleware(AuthMiddleware, settings=settings)

    client = TestClient(app)
    r = client.get("/secure", headers={"Authorization": "Bearer fake.jwt.token"})
    assert r.status_code == 401
    assert "Invalid token" in r.json()["detail"]
