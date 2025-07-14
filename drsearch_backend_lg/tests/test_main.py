from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.main import app
from app.routers.chat import agent as chat_agent
from app.routers.documents import store as doc_store

client = TestClient(app)

chat_agent.run = AsyncMock(return_value={"response": "hi", "context": [], "timestamp": "now"})
doc_store.add_document = AsyncMock(return_value=1)

def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"message": "LangGraph RAG API is running!"}

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}

def test_chat_query(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    from importlib import reload
    import app.main as main_reload
    reload(main_reload)
    c = TestClient(main_reload.app)
    resp = c.post("/chat/query", json={"query": "hi", "user_id": "u"})
    assert resp.status_code == 200
    assert resp.json()["response"] == "hi"

def test_document_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    from importlib import reload
    import app.main as main_reload
    reload(main_reload)
    c = TestClient(main_reload.app)
    fpath = tmp_path / "a.txt"
    fpath.write_text("hello")
    with open(fpath, "rb") as f:
        resp = c.post("/documents/upload", files={"file": ("a.txt", f, "text/plain")})
    assert resp.status_code == 200
    assert resp.json()["filename"] == "a.txt"
