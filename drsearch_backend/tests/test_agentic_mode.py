import os

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""
os.environ["LOG_OUTPUT_MODE"] = "local"

from langchain.schema.runnable import RunnableLambda


def test_get_answer_chain_agent_mode(monkeypatch):
    monkeypatch.setenv("RAG_PROCESSING_MODE", "agent")
    from importlib import reload

    from app.core import chain_config

    reload(chain_config)
    from app.chain import api

    reload(api)

    called = {}

    def fake_build(index_name: str) -> RunnableLambda:
        called["index"] = index_name

        def _invoke(inputs: dict) -> str:
            return "AGENT"

        return RunnableLambda(_invoke)

    monkeypatch.setattr(api, "build_agent_chain", fake_build)

    chain = api.get_answer_chain("IDX", num_docs=2)
    result = chain.invoke({"question": "hi", "chat_history": []})

    assert result == "AGENT"
    assert called["index"] == "IDX"

    monkeypatch.setenv("RAG_PROCESSING_MODE", "classic")
    reload(chain_config)
    reload(api)
