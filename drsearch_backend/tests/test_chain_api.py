import types
from app.chain import api


def test__engine_for_creates_and_caches(monkeypatch):
    # Clear the engine cache to start fresh
    api._engine_cache.clear()

    dummy_chain = object()

    class DummyChatEngine:
        def __init__(self, index_name):
            self.index_name = index_name
            self.answer_chain = dummy_chain

    monkeypatch.setattr("app.chain.api.ChatEngine", DummyChatEngine)

    # First call – should instantiate
    engine = api._engine_for("TEST_INDEX", 3)
    assert isinstance(engine, DummyChatEngine)
    assert engine.index_name == "TEST_INDEX"
    assert engine.answer_chain is dummy_chain

    # Second call – should hit cache
    cached = api._engine_for("TEST_INDEX", 3)
    assert cached is engine


def test_get_answer_chain(monkeypatch):
    dummy_chain = object()

    class DummyChatEngine:
        def __init__(self, index_name):
            self.answer_chain = dummy_chain

    monkeypatch.setattr("app.chain.api.ChatEngine", DummyChatEngine)
    api._engine_cache.clear()

    # Should use default index if None passed
    result = api.get_answer_chain(None, 3)
    assert result is dummy_chain

    # Should use custom index
    result2 = api.get_answer_chain("ALT_INDEX", 3)
    assert result2 is dummy_chain


def test_answer_chain_lambda(monkeypatch):
    dummy_chain = object()

    class DummyChatEngine:
        def __init__(self, index_name):
            self.answer_chain = dummy_chain

    monkeypatch.setattr("app.chain.api.ChatEngine", DummyChatEngine)
    api._engine_cache.clear()

    # Call the global RunnableLambda (simulate LangChain request input)
    result = api.answer_chain.invoke(
        {"index_name": "JACSKE_Program", "num_docs_retrieved": 3}
    )
    assert result is dummy_chain
