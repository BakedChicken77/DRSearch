import pytest
from app.chain.engine import ChatEngine
from app.chain.exceptions import ConfigurationError
from langchain_core.runnables import RunnableLambda
from langchain.schema import Document
from langchain_core.language_models.fake import FakeListLLM
from tests.conftest import _DummyRetriever  # type: ignore


class DummyLLM:
    def __call__(self, input, **kwargs):
        return "LLM-OK"


dummy_llm = RunnableLambda(DummyLLM())


def test_chat_engine_unknown_index():
    with pytest.raises(ConfigurationError):
        ChatEngine("does-not-exist")


def test_chat_engine_answer_chain_simple_RAG_OFF(monkeypatch):
    # Force RAG mode off so retriever chain is skipped -> simpler test
    monkeypatch.setattr("app.chain.engine.RAG_ON", False)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", False)

    eng = ChatEngine()  # default index

    # minimal invoke – chain returns whatever DummyLLM returns
    out = eng.answer_chain.invoke(
        {"question": "hi", "chat_history": [], "index_name": None}
    )
    assert out == "LLM-OK"


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

    eng = ChatEngine()  # default index

    out = eng.answer_chain.invoke({"question": "hi", "chat_history": []})
    assert out == "LLM-OK"


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
