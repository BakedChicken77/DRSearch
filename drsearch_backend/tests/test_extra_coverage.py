import importlib
import runpy
import sys
from pathlib import Path

import builtins
import pytest
import os

from app.chain.cli import _cli as chain_cli
from app.chain.mapping import PartNumberMapping
from app.models import ChatRequest
from app.core.config import Settings
from app.index_options import INDEX_OPTIONS
from tests.conftest import _DummyRetriever  # type: ignore


class _StubChain:
    def __init__(self, reply: str):
        # LangChain Runnable minimal stub with invoke()
        self._reply = reply

    def invoke(self, *_a, **_k):  # noqa: D401
        return self._reply


class _StubEngine:
    def __init__(self, reply: str):
        self.answer_chain = _StubChain(reply)


def test_cli_one_shot(monkeypatch, capsys):
    """Exercise the CLI's one-shot path to cover app/chain/cli.py."""
    # Pretend we're executing:  python -m app.chain.cli -q hi
    monkeypatch.setattr(sys, "argv", ["prog", "-q", "hi"])

    # Patch the private helper so no heavy initialisation occurs.
    monkeypatch.setattr("app.chain.cli._engine_for", lambda idx: _StubEngine("hello"))

    # Run the CLI entry function directly.
    chain_cli()

    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_cli_interactive_exit(monkeypatch, capsys):
    """Run the CLI interactive path but immediately exit to cover remaining lines."""

    # No -q argument so CLI enters interactive mode.
    monkeypatch.setattr(sys, "argv", ["prog"])

    # Simulate two user inputs: an actual question followed by 'exit'.
    user_inputs = iter(["what?", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _p="": next(user_inputs))

    # The stub engine will echo back "stub-response" so the AI path is taken.
    monkeypatch.setattr(
        "app.chain.cli._engine_for", lambda idx: _StubEngine("stub-response")
    )

    chain_cli()

    captured = capsys.readouterr()
    # Should greet user and then print AI response
    assert "Interactive RAG chat" in captured.out
    assert "stub-response" in captured.out


def test_mapping_no_file(tmp_path):
    """Cover the branch where the mapping CSV does *not* exist."""
    mapping = PartNumberMapping("does_not_exist.csv")
    assert mapping.data is None  # triggers the early-exit branch


def test_models_chat_request():
    """Ensure the Pydantic model validates and serialises as expected."""
    req = ChatRequest(
        question="q",
        chat_history=[{"human": "h", "ai": "a"}],
        index_name="idx",
        num_docs_retrieved=4,
    )
    data = req.dict()
    assert data["question"] == "q"
    assert data["chat_history"][0]["human"] == "h"
    assert data["index_name"] == "idx"
    assert data["num_docs_retrieved"] == 4


def test_settings_split_origins():
    """Validate the custom CORS origins validator in core.config.Settings."""
    # Ensure any existing env-var does not interfere with constructor-provided value
    os.environ.pop("CORS_ORIGINS", None)

    cfg = Settings(
        cors_origins="http://a.com , http://b.com", tenant_id="t", client_id="c"
    )
    assert cfg.cors_origins == ["http://a.com", "http://b.com"]


def test_index_options_structure():
    """Simple structural sanity check for INDEX_OPTIONS list."""
    assert isinstance(INDEX_OPTIONS, list) and INDEX_OPTIONS, "Empty index options list"
    for item in INDEX_OPTIONS:
        assert {"name", "display_name", "example_questions"}.issubset(item)
        assert (
            isinstance(item["example_questions"], list) and item["example_questions"]
        ), "Missing questions"


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_main_module_execution(monkeypatch):
    """Run the *app.main* module as ``__main__`` while stubbing heavy deps."""

    # Stub uvicorn.Server so no network is opened
    class _DummyServer:
        def __init__(self, *a, **k):
            pass

        async def serve(self):  # noqa: D401 – must be async
            return None

    monkeypatch.setattr("uvicorn.Server", _DummyServer)

    # Stub uvicorn.Config because we don't need its logic
    monkeypatch.setattr("uvicorn.Config", lambda *a, **k: object())

    # Prevent real signal handling on non-main threads / platforms
    monkeypatch.setattr(
        "asyncio.AbstractEventLoop.add_signal_handler",
        lambda *a, **k: None,
        raising=False,
    )

    # Replace asyncio.new_event_loop with a dummy loop that has the required methods.
    import asyncio

    class _FakeLoop:
        def add_signal_handler(self, *a, **k):
            pass

        def run_until_complete(self, coro):
            pass

    monkeypatch.setattr(asyncio, "new_event_loop", lambda: _FakeLoop())
    monkeypatch.setattr(asyncio, "set_event_loop", lambda *a, **k: None)

    # Provide a valid CORS_ORIGINS so Settings() validates successfully
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    # Finally run the module as if it were the main program. The patched pieces
    # ensure nothing heavyweight actually happens.
    runpy.run_module("app.main", run_name="__main__")


def test_engine_modify_docs_mapping_none(monkeypatch):
    """Cover the branch where _modify_docs early-returns when mapping is None."""
    from app.chain.engine import ChatEngine
    from langchain.schema import Document
    from langchain_core.runnables import RunnableLambda

    # Force RAG_ON so retriever logic is active but patch everything heavy.
    monkeypatch.setattr("app.chain.engine.RAG_ON", True)
    monkeypatch.setattr("app.core.chain_config.RAG_ON", True)
    monkeypatch.setattr(
        "app.chain.retriever.RetrieverFactory.build", lambda *_, **__: _DummyRetriever()
    )

    # Lightweight LLM replacement
    monkeypatch.setattr(
        "app.chain.engine.AzureChatOpenAI",
        lambda *_, **__: RunnableLambda(lambda *_a, **_k: "text"),
    )

    eng = ChatEngine("SEPs_F_T_C_W_A_V")  # This index has PN_TO_FILE_MAPPING = None

    # Simple retriever returning a doc without file_path metadata.
    retr = RunnableLambda(
        lambda q: [Document(page_content="x", metadata={"filename": "ignored.pdf"})]
    )

    chain = eng._build_retriever_chain(retr, lambda d: "")
    docs = chain.invoke({"question": "hi", "chat_history": []})

    # _modify_docs should be a pass-through because mapping is None.
    assert docs[0].metadata.get("file_path") is None


def test_import_chat_chain():
    """Importing ``app.chat_chain`` should succeed and cover the module-level code."""
    import importlib

    module = importlib.import_module("app.chat_chain")
    assert hasattr(module, "_cli")


def test_cli_keyboard_interrupt(monkeypatch, capsys):
    """Trigger the KeyboardInterrupt branch in the CLI to reach 100% coverage."""
    monkeypatch.setattr(sys, "argv", ["prog"])

    # Engine stub not used because we interrupt before any question is asked.
    monkeypatch.setattr("app.chain.cli._engine_for", lambda idx: _StubEngine("unused"))

    # input will raise KeyboardInterrupt immediately.
    def _raise_interrupt(_p=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", _raise_interrupt)

    chain_cli()

    captured = capsys.readouterr()
    assert "Exiting." in captured.out
