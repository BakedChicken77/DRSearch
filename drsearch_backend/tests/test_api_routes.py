import json
import pathlib
import os
from fastapi.testclient import TestClient
import types

async def _ok():
    return [{"name": "x"}]

def test_index_options_happy_path(fastapi_client: TestClient, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes._read_index_options", _ok)
    monkeypatch.setattr("app.warmup.INDEX_STATUS", {"x": True})
    monkeypatch.setattr("app.api.v1.routes.INDEX_STATUS", {"x": True})
    r = fastapi_client.get("/index-options")
    assert r.status_code == 200
    data = r.json()["result"][0]
    assert data["name"] == "x"
    assert data["initialized"] is True


def test_feedback_create_and_patch(fastapi_client: TestClient):
    body = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "key": "user_score",
        "score": 1,
    }
    # POST
    assert fastapi_client.post("/feedback", json=body).status_code == 200
    # PATCH w/out feedback_id -> 400
    # assert fastapi_client.patch("/feedback", json=body).status_code == 400
    assert fastapi_client.patch("/feedback", json=body).status_code == 400
    # PATCH ok
    body["feedback_id"] = "22222222-2222-2222-2222-222222222222"
    assert fastapi_client.patch("/feedback", json=body).status_code == 200


def test_get_trace_not_implemented(fastapi_client: TestClient):
    r = fastapi_client.post(
        "/get_trace", json={"run_id": "11111111-1111-1111-1111-111111111111"}
    )
    assert r.status_code == 501


def test_file_proxy_404(fastapi_client: TestClient):
    # path mocked to *not* exist
    r = fastapi_client.get("/files/does/not/exist.pdf")
    assert r.status_code == 404


def test_file_proxy_ok(fastapi_client: TestClient, monkeypatch, tmp_path):
    # create a dummy file
    the_file = tmp_path / "a.pdf"
    the_file.write_bytes(b"%PDF-1.4")
    # patch os.path.exists
    monkeypatch.setattr("os.path.exists", lambda p: True)
    # patch os.path.basename
    monkeypatch.setattr("os.path.basename", lambda p: "a.pdf")
    # patch FileResponse to bypass file-io
    monkeypatch.setattr(
        "app.api.v1.routes.FileResponse", lambda *_, **__: types.SimpleNamespace()
    )
    assert (
        fastapi_client.get("/files/a.pdf?dummy").status_code == 200
    )  # returned by dummy FileResponse


def test_patch_feedback_missing_id(fastapi_client):
    body = {
        "score": 1,
        "comment": "missing id"
    }
    r = fastapi_client.patch("/feedback", json=body)
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing feedback_id"

def test_patch_feedback_null_id(fastapi_client):
    body = {
        "feedback_id": None,
        "score": 1
    }
    r = fastapi_client.patch("/feedback", json=body)
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing feedback_id"
