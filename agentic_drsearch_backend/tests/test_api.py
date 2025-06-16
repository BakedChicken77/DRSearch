from httpx import AsyncClient
from app.main import app

async def test_query():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/query", json={"question": "Hello"})
        assert resp.status_code == 200
        assert "answer" in resp.json()
