def test__agent_for_creates_and_caches(monkeypatch):
    from app.agent import rag_agent as api

    api._agent_cache.clear()
    monkeypatch.setattr(api, "RAG_ON", False)

    class DummyLLM:
        def __init__(self, *_, **__):
            pass

        def bind(self, **kwargs):
            return lambda *_a, **_k: None

    class DummyExec:
        def __init__(self, *_, **__):
            pass

        def __call__(self, *_, **__):
            return None

    monkeypatch.setattr(api, "AzureChatOpenAI", DummyLLM)
    monkeypatch.setattr(api, "AgentExecutor", DummyExec)

    first = api.get_agent_executor("IDX", 3)
    second = api.get_agent_executor("IDX", 3)
    assert first is second


def test_get_agent_executor(monkeypatch):
    from app.agent import rag_agent as api

    dummy = object()
    monkeypatch.setattr(api, "_agent_for", lambda *_, **__: dummy)
    assert api.get_agent_executor(None, 2) is dummy
    assert api.get_agent_executor("ALT", 2) is dummy
