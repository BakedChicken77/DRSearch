# file: app/chain/api.py
"""LangChain API helpers with optional Langfuse tracing."""

from __future__ import annotations

from typing import Dict, Tuple, Sequence
import json
from langchain.schema import Document
from langchain.schema.runnable import Runnable, RunnableLambda
from langfuse.callback import CallbackHandler

from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED

_engine_cache: Dict[Tuple[str, int], ChatEngine] = {}


class _LangfuseCallbackHandler(CallbackHandler):  # pylint: disable=too-many-ancestors
    """Langfuse handler that makes retriever outputs JSON serializable."""

    @staticmethod
    def _serialize_docs(documents: Sequence[Document]) -> list[dict]:
        """Return docs with metadata values converted to strings when needed."""
        def _safe(value: object) -> object:
            try:
                json.dumps(value)
                return value
            except TypeError:
                return str(value)

        return [
            {
                "page_content": doc.page_content,
                "metadata": {k: _safe(v) for k, v in doc.metadata.items()},
            }
            for doc in documents
        ]

    def on_retriever_end(  # type: ignore[override]
        self,
        documents: Sequence[Document],
        *,
        run_id,
        parent_run_id=None,
        **kwargs,
    ) -> None:
        serializable = self._serialize_docs(documents)
        super().on_retriever_end(
            serializable, run_id=run_id, parent_run_id=parent_run_id, **kwargs
        )


def _new_langfuse_handler() -> CallbackHandler | None:
    """Create a new Langfuse handler if environment variables are set."""
    try:
        return _LangfuseCallbackHandler()
    except Exception:  # pragma: no cover - missing env vars  # pylint: disable=broad-except
        return None


def _engine_for(index_name: str, num_docs: int) -> ChatEngine:
    """Retrieve or create a cached ChatEngine for the given index and k."""
    key = (index_name, num_docs)
    if key not in _engine_cache:
        # Update global setting before engine creation
        from app.core import chain_config  # pylint: disable=import-outside-toplevel

        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs  # pylint: disable=protected-access
        _engine_cache[key] = ChatEngine(index_name)
    return _engine_cache[key]


def get_answer_chain(
    index_name: str | None = None,
    num_docs: int = _NUMBER_OF_DOCS_RETRIEVED,
    trace: bool = True,
) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    chain = _engine_for(index_name or _DEFAULT_INDEX, num_docs).answer_chain
    if trace and hasattr(chain, "with_config"):
        handler = _new_langfuse_handler()
        if handler:
            return chain.with_config(callbacks=[handler])
    return chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
