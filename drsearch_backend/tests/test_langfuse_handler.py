"""Tests for Langfuse callback handler and environment gating."""

from __future__ import annotations

import importlib
import sys

from langchain.schema import Document


def test_serialize_docs_handles_non_serializable_metadata(monkeypatch) -> None:
    """Ensure documents with complex metadata can be serialized to JSON."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    api = importlib.reload(importlib.import_module("app.chain.api"))

    docs = [Document(page_content="foo", metadata={"a": object()})]
    handler = api._LangfuseCallbackHandler(  # pylint: disable=protected-access
        public_key="pk", secret_key="sk", host="http://localhost", enabled=False
    )

    serialized = handler._serialize_docs(docs)  # pylint: disable=protected-access
    # Should be convertible to JSON without raising
    import json

    json.dumps(serialized)
    assert serialized[0]["page_content"] == "foo"


def test_langfuse_disabled_skips_import(monkeypatch) -> None:
    """Langfuse library is not imported when disabled."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    sys.modules.pop("langfuse", None)
    sys.modules.pop("langfuse.callback", None)
    api = importlib.reload(importlib.import_module("app.chain.api"))

    assert "langfuse" not in sys.modules
    assert api._new_langfuse_handler() is None  # pylint: disable=protected-access

