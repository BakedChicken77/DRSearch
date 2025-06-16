import httpx
import pytest
from app.main import app
from app.api.v1 import routes
from app.rag_agents import agent

@pytest.mark.asyncio
async def test_query(mocker):
    async def fake_run_agent(question: str) -> str:
        return "mock-answer"

    mocker.patch.object(routes, "run_agent", fake_run_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/query", json={"question": "Hello"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "mock-answer"
