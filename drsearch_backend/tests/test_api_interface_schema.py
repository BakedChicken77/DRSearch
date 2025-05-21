from fastapi.testclient import TestClient
from app.models import IndexOptionsResponse, StandardResponse

async def _dummy_index_options():
    return [{"name": "idx", "display_name": "Index", "example_questions": ["q"]}]

def test_index_options_schema(fastapi_client: TestClient, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes._read_index_options", _dummy_index_options)
    response = fastapi_client.get("/index-options")
    assert response.status_code == 200
    data = IndexOptionsResponse(**response.json())
    assert data.code == 200
    assert data.result[0].name == "idx"

def test_feedback_roundtrip_schema(fastapi_client: TestClient):
    base = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "key": "user_score",
        "score": 1,
    }
    post = fastapi_client.post("/feedback", json=base)
    assert post.status_code == 200
    post_data = StandardResponse(**post.json())
    assert post_data.code == 200
    patch_body = {**base, "feedback_id": "22222222-2222-2222-2222-222222222222"}
    patch = fastapi_client.patch("/feedback", json=patch_body)
    assert patch.status_code == 200
    patch_data = StandardResponse(**patch.json())
    assert patch_data.result.startswith("patched")
