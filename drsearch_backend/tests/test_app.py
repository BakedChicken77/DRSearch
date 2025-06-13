# file: tests/test_app.py

"""High‑level integration tests exercising the public API surface."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import create_app


@pytest.fixture()
def client() -> Any:  # type: ignore[valid-type] – TestClient has no stub
    """Yields a FastAPI TestClient with *auth_enabled* disabled via monkeypatch."""

    app = create_app()
    app.dependency_overrides = {}  # clear any overrides if present
    return TestClient(app)


def test_index_options(client):
    r = client.get("/index-options")
    assert r.status_code == 200
    assert "result" in r.json()


# def test_chat_requires_body(client):
#     r = client.post("/chat/stream", json={})
#     # FastAPI will reject missing fields => 422 Unprocessable Entity
#     # assert r.status_code == 422
#     assert r.status_code == 200
def test_chat_requires_body(fastapi_client: TestClient):
    response = fastapi_client.post("/chat/invoke")
    assert response.status_code == 422
