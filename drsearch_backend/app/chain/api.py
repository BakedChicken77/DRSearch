# file: app/chain/api.py

from __future__ import annotations

from typing import Dict, Tuple
from langchain.schema.runnable import Runnable, RunnableLambda
import os

from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED

_engine_cache: Dict[Tuple[str, int], ChatEngine] = {}


def _engine_for(index_name: str, num_docs: int) -> ChatEngine:
    """Retrieve or create a cached ChatEngine for the given index and k."""
    key = (index_name, num_docs)

    # Always create a fresh ChatEngine instance when running with the in-memory
    # ``FakeStreamingListLLM``. This avoids returning a cached engine that was
    # initialised in a previous test (or request) and therefore ensures that
    # patches/mocks applied to ``ChatEngine._init_llm`` take effect.

    llm_service = os.getenv("LLM_SERVICE", "azure").lower()

    # When using the fake LLM (e.g. in unit/integration tests) we skip the
    # cache altogether so that each request gets a brand-new engine.  This
    # behaviour keeps production performance (where caching still applies)
    # while making the system easier to test.
    if llm_service == "fake":
        from app.core import chain_config

        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
        return ChatEngine(index_name)

    if key not in _engine_cache:
        # Update global setting before engine creation
        from app.core import chain_config

        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
        _engine_cache[key] = ChatEngine(index_name)
    return _engine_cache[key]


def get_answer_chain(index_name: str | None = None, num_docs: int = _NUMBER_OF_DOCS_RETRIEVED) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    return _engine_for(index_name or _DEFAULT_INDEX, num_docs).answer_chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
