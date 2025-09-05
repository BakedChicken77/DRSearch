# file: app/chain/api.py
"""LangChain API helpers with optional Langfuse tracing."""

from __future__ import annotations

from typing import Dict, Tuple
from langchain.schema.runnable import Runnable, RunnableLambda
from langfuse.callback import CallbackHandler

from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED

_engine_cache: Dict[Tuple[str, int], ChatEngine] = {}
_langfuse_handler = CallbackHandler()


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
) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    chain = _engine_for(index_name or _DEFAULT_INDEX, num_docs).answer_chain
    if hasattr(chain, "with_config"):
        return chain.with_config(callbacks=[_langfuse_handler])
    return chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
