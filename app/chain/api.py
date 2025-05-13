# file: app/chain/api.py

from __future__ import annotations

from typing import Dict
from langchain.schema.runnable import Runnable, RunnableLambda

from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX

_engine_cache: Dict[str, ChatEngine] = {}


def _engine_for(index_name: str) -> ChatEngine:
    """Retrieve or create a cached ChatEngine for the given index."""
    if index_name not in _engine_cache:
        _engine_cache[index_name] = ChatEngine(index_name)
    return _engine_cache[index_name]


def get_answer_chain(index_name: str | None = None) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    return _engine_for(index_name or _DEFAULT_INDEX).answer_chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(inputs.get("index_name", _DEFAULT_INDEX))
)
