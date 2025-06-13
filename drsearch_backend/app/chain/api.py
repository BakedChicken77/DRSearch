# file: app/chain/api.py

from __future__ import annotations

from typing import Dict, Tuple

from langchain.schema.runnable import Runnable, RunnableLambda

from app.chain.agent_engine import build_agent_chain
from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED, RAG_MODE

_engine_cache: Dict[Tuple[str, int], ChatEngine] = {}
_agent_cache: Dict[Tuple[str, int], Runnable] = {}


def _engine_for(index_name: str, num_docs: int) -> ChatEngine:
    """Retrieve or create a cached ChatEngine for the given index and k."""
    key = (index_name, num_docs)
    if key not in _engine_cache:
        # Update global setting before engine creation
        from app.core import chain_config

        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
        _engine_cache[key] = ChatEngine(index_name)
    return _engine_cache[key]


def get_answer_chain(
    index_name: str | None = None, num_docs: int = _NUMBER_OF_DOCS_RETRIEVED
) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    idx = index_name or _DEFAULT_INDEX
    if RAG_MODE == "agent":
        key = (idx, num_docs)
        if key not in _agent_cache:
            from app.core import chain_config

            chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
            _agent_cache[key] = build_agent_chain(idx)
        return _agent_cache[key]

    return _engine_for(idx, num_docs).answer_chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
