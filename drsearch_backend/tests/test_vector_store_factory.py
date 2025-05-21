from app.vector_store import get_vector_store, WeaviateVectorStore, PgVectorStore


def test_get_vector_store_default(monkeypatch):
    monkeypatch.delenv("VECTOR_BACKEND", raising=False)
    store = get_vector_store("idx", text_key="text", attributes=[])
    assert isinstance(store, WeaviateVectorStore)


def test_get_vector_store_pgvector(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "pgvector")
    monkeypatch.setenv("PGVECTOR_CONNECTION", "postgresql://user:pass@host/db")

    class Dummy(PgVectorStore):
        def __init__(self, index_name: str) -> None:  # pragma: no cover
            self.index_name = index_name

    monkeypatch.setattr("app.vector_store.factory.PgVectorStore", Dummy)
    store = get_vector_store("idx", text_key="text", attributes=[])
    assert isinstance(store, Dummy)
