import pytest
from fastapi.testclient import TestClient


def test_chat_requires_body(fastapi_client: TestClient):
    response = fastapi_client.post("/chat/invoke")
    assert response.status_code == 422
