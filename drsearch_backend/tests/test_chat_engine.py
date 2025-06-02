import pytest
from langchain.schema import Document
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.runnables import RunnableLambda
from langchain.prompts import ChatPromptTemplate

from app import System_Prompts

from app.chain.engine import ChatEngine
from tests.conftest import _DummyRetriever  # type: ignore


class DummyLLM:
    def __call__(self, input, **kwargs):
        return "LLM-OK"


dummy_llm = RunnableLambda(DummyLLM())


class _ConstantLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def __call__(self, *_, **__):
        return self._reply

    def invoke(self, *_, **__):
        return self._reply


def test_chat_engine_unknown_index(monkeypatch):
    """Unknown index should default to chatbot-only mode."""

    captured: dict[str, str] = {}
    orig_from_messages = ChatPromptTemplate.from_messages

    def capture(msgs):
        captured["system"] = msgs[0][1]
        return orig_from_messages(msgs)

    monkeypatch.setattr(
        "app.chain.engine.ChatPromptTemplate.from_messages",
        capture,
    )

    eng = ChatEngine("does-not-exist")
    out = eng.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"
    assert captured["system"] == System_Prompts.RESPONSE_TEMPLATE_CHATBOT


def test_chat_engine_answer_chain_simple_RAG_OFF(monkeypatch):
    """When RAG disabled, system prompt should use chatbot template."""

    monkeypatch.setattr("app.chain.engine.RAG_ON", False)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", False)

    captured: dict[str, str] = {}

    orig_from_messages = ChatPromptTemplate.from_messages

    def capture(msgs):
        captured["system"] = msgs[0][1]
        return orig_from_messages(msgs)

    monkeypatch.setattr(
        "app.chain.engine.ChatPromptTemplate.from_messages",
        capture,
    )

    eng = ChatEngine()

    out = eng.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"
    assert captured["system"] == System_Prompts.RESPONSE_TEMPLATE_CHATBOT


def test_chat_engine_answer_chain_simple_RAG_ON(monkeypatch):
    """Full RAG chain incl. MultiQueryRetriever should succeed with FakeListLLM."""

    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    # Ensure retriever chain uses a predictable in-memory retriever instead of
    # the real Weaviate vector-store, which is outside the scope of unit tests.
    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: _DummyRetriever(),
    )

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )
    monkeypatch.setattr(
        "app.chain.engine.ChatEngine._init_gating_llm",
        lambda self: _ConstantLLM("yes"),
    )

    eng = ChatEngine()  # default index

    out = eng.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"


def test_chat_engine_retriever_failure(monkeypatch):
    """ChatEngine should fall back to chatbot mode if retriever init fails."""

    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.chain.retriever.RetrieverFactory.build", boom)

    captured: dict[str, str] = {}
    orig_from_messages = ChatPromptTemplate.from_messages

    def capture(msgs):
        captured["system"] = msgs[0][1]
        return orig_from_messages(msgs)

    monkeypatch.setattr(
        "app.chain.engine.ChatPromptTemplate.from_messages",
        capture,
    )

    eng = ChatEngine()

    out = eng.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"
    assert captured["system"] == System_Prompts.RESPONSE_TEMPLATE_CHATBOT


def test_llm_init_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.chain.engine.AzureChatOpenAI", boom)

    with pytest.raises(RuntimeError, match="boom"):
        ChatEngine("JACSKE_Program")  # any valid key from INDEX_CONFIG


def test_multiquery_retriever_path(monkeypatch):
    from app.chain.engine import ChatEngine

    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: _DummyRetriever(),
    )

    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )

    ChatEngine("JACSKE_Program")  # should initialise without error


def test_context_map_with_retriever(monkeypatch):
    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("answer"),
    )
    monkeypatch.setattr(
        "app.chain.engine.ChatEngine._init_gating_llm",
        lambda self: _ConstantLLM("yes"),
    )
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    from tests.conftest import _DummyRetriever  # type: ignore

    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: _DummyRetriever(),
    )

    engine = ChatEngine("JACSKE_Program")

    result = engine.answer_chain.invoke({"question": "test?", "chat_history": []})
    assert "answer" in result


def test_modify_docs_enriches_path(monkeypatch, tmp_path):
    csv_content = "file_name,Downloaded File\nabc.pdf,\\\\server\\abc.pdf\n"
    mapping_file = tmp_path / "JACSKE_PROD_DEPLOY.csv"
    mapping_file.write_text(csv_content, encoding="utf-8")

    monkeypatch.setattr("app.chain.mapping._MAPPING_DIR", tmp_path)

    # Ensure retriever chain uses a predictable in-memory retriever instead of
    # the real Weaviate vector-store, which is outside the scope of unit tests.
    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: _DummyRetriever(),
    )

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )

    engine = ChatEngine("JACSKE_Program")

    retriever = RunnableLambda(
        lambda input: [Document(page_content="...", metadata={"filename": "abc.pdf"})]
    )

    format_fn = lambda docs: "<doc>content</doc>"

    chain = engine._build_retriever_chain(retriever, format_fn)
    out = chain.invoke({"question": "test", "chat_history": []})
    assert out[0].metadata["file_path"] == "\\\\server\\abc.pdf"


def test_gating_skips_retrieval(monkeypatch):
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)
    monkeypatch.setattr("app.chain.engine.RETRIEVAL_GATING_ON", True)
    monkeypatch.setattr("app.core.chain_config.RETRIEVAL_GATING_ON", True)

    called = {"retrieved": False}

    class RecordingRetriever(_DummyRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
            called["retrieved"] = True
            return super()._get_relevant_documents(query, run_manager=run_manager)

    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: RecordingRetriever(),
    )

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _ConstantLLM("LLM-OK"),
    )
    monkeypatch.setattr(
        "langchain.retrievers.multi_query.MultiQueryRetriever.from_llm",
        lambda *_, **__: _DummyRetriever(),
    )
    monkeypatch.setattr(
        "app.chain.engine.ChatEngine._init_gating_llm",
        lambda self: _ConstantLLM("no"),
    )

    engine = ChatEngine("JACSKE_Program")

    out = engine.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"
    assert called["retrieved"] is False


def test_gating_allows_retrieval(monkeypatch):
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)
    monkeypatch.setattr("app.chain.engine.RETRIEVAL_GATING_ON", True)
    monkeypatch.setattr("app.core.chain_config.RETRIEVAL_GATING_ON", True)

    called = {"retrieved": False}

    class RecordingRetriever(_DummyRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore[override]
            called["retrieved"] = True
            return super()._get_relevant_documents(query, run_manager=run_manager)

    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: RecordingRetriever(),
    )

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )
    monkeypatch.setattr(
        "app.chain.engine.ChatEngine._init_gating_llm",
        lambda self: _ConstantLLM("yes"),
    )

    engine = ChatEngine("JACSKE_Program")

    out = engine.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"
    assert called["retrieved"] is True


# Helper to build a deterministic FakeListLLM for test scenarios
def _fake_llm_for_answer(final_answer: str) -> FakeListLLM:
    """Return a FakeListLLM whose second call yields *final_answer*.

    The first call produces three newline-separated sub-queries so that
    ``MultiQueryRetriever`` can function correctly.
    """

    return FakeListLLM(responses=["q1\nq2\nq3", final_answer])


def _dup_test_chat_engine_answer_chain_simple_RAG_ON_fake(monkeypatch):
    # Force RAG mode off so retriever chain is skipped -> simpler test
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    # Use a FakeListLLM that returns predictable values for MultiQueryRetriever.
    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )

    eng = ChatEngine()  # default index

    # minimal invoke – chain returns whatever DummyLLM returns
    out = eng.answer_chain.invoke(
        {"question": "hi", "chat_history": [], "index_name": None}
    )
    assert out == "LLM-OK"


def _dup_test_multiquery_retriever_path_fake(monkeypatch):
    from app.chain.engine import ChatEngine

    # Use a FakeListLLM that returns predictable values for MultiQueryRetriever.
    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    ChatEngine("JACSKE_Program")  # this will now succeed


def _dup_test_context_map_with_retriever_fake(monkeypatch):
    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("answer"),
    )
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    engine = ChatEngine("JACSKE_Program")

    result = engine.answer_chain.invoke(
        {
            "question": "test?",
            "chat_history": [],
        }
    )
    assert "answer" in result


def _dup_test_modify_docs_enriches_path_fake(monkeypatch, tmp_path):
    csv_content = "file_name,Downloaded File\nabc.pdf,\\\\server\\abc.pdf\n"
    mapping_file = tmp_path / "JACSKE_PROD_DEPLOY.csv"
    mapping_file.write_text(csv_content, encoding="utf-8")

    monkeypatch.setattr("app.chain.mapping._MAPPING_DIR", tmp_path)

    # Ensure retriever chain uses a predictable in-memory retriever instead of
    # the real Weaviate vector-store, which is outside the scope of unit tests.
    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build",
        lambda *_, **__: _DummyRetriever(),
    )

    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)

    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: _fake_llm_for_answer("LLM-OK"),
    )

    engine = ChatEngine("JACSKE_Program")

    retriever = RunnableLambda(
        lambda input: [Document(page_content="...", metadata={"filename": "abc.pdf"})]
    )

    format_fn = lambda docs: "<doc>content</doc>"

    chain = engine._build_retriever_chain(retriever, format_fn)
    out = chain.invoke({"question": "test", "chat_history": []})
    assert out[0].metadata["file_path"] == "\\\\server\\abc.pdf"
