import os
import httpx
import pytest

# Minimal env vars so Settings can load during tests
os.environ.setdefault("PGVECTOR_URL", "postgresql://user:pass@localhost/db")
os.environ.setdefault("PGVECTOR_INDEX", "test")
os.environ.setdefault("AZURE_OPENAI_LLM_DEPLOYMENT", "gpt4")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "dummy")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-10-21")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example.com")
os.environ.setdefault("AZURE_OPENAI_EMBEDDER", "text-embedding-ada-002")

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
