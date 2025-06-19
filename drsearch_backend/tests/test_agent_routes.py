from fastapi.testclient import TestClient


def test_agent_chat_requires_body(fastapi_client: TestClient):
    response = fastapi_client.post("/agent-chat/invoke")
    assert response.status_code == 422
