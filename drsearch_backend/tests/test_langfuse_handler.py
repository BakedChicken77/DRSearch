"""Tests for the Langfuse callback handler serialization helper."""

from __future__ import annotations

import json

from langchain.schema import Document

from app.chain.api import _LangfuseCallbackHandler


def test_serialize_docs_handles_non_serializable_metadata() -> None:
    """Ensure documents with complex metadata can be serialized to JSON."""
    docs = [Document(page_content="foo", metadata={"a": object()})]

    handler = _LangfuseCallbackHandler(
        public_key="pk", secret_key="sk", host="http://localhost", enabled=False
    )

    serialized = handler._serialize_docs(docs)
    # Should be convertible to JSON without raising
    json.dumps(serialized)
    assert serialized[0]["page_content"] == "foo"
