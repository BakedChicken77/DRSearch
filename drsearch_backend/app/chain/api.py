# drsearch_backend/app/chain/api.py

# file: app/chain/api.py
"""LangChain API helpers with optional Langfuse tracing."""

from __future__ import annotations

from typing import Dict, Tuple
from langchain.schema.runnable import Runnable, RunnableLambda
from app.chain.engine import ChatEngine
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED
from app.core.config import get_settings
from app.core import chain_config

settings = get_settings()

LANGFUSE_ENABLED = settings.langfuse_enabled

if LANGFUSE_ENABLED:
    from langfuse.callback import CallbackHandler
else:  # pragma: no cover - executed only when Langfuse disabled
    class CallbackHandler:  # pylint: disable=too-few-public-methods
        """Placeholder handler when Langfuse is disabled."""

_engine_cache: Dict[Tuple[str, int], ChatEngine] = {}


def _new_langfuse_handler() -> CallbackHandler | None:
    """Create a new Langfuse handler if environment variables are set."""
    if not LANGFUSE_ENABLED:
        return None
    try:
        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:  # pragma: no cover - missing env vars  # pylint: disable=broad-except
        return None


def _engine_for(index_name: str, num_docs: int, page_window: int) -> ChatEngine:
    key = (index_name, num_docs, page_window)
    if key not in _engine_cache:
        # Update globals before engine creation so retriever sees them
        from app.core import chain_config as cfg  # pylint: disable=import-outside-toplevel
        cfg._NUMBER_OF_DOCS_RETRIEVED = num_docs          # noqa: SLF001
        cfg._PAGE_WINDOW = page_window                     
        _engine_cache[key] = ChatEngine(index_name)
    return _engine_cache[key]


def get_answer_chain(
    index_name: str | None = None,
    num_docs: int = _NUMBER_OF_DOCS_RETRIEVED,
    page_window: int = chain_config._PAGE_WINDOW,   
    trace: bool = True,
) -> Runnable:
    """Return the langchain Runnable for the specified index (cached)."""
    chain = _engine_for(index_name or _DEFAULT_INDEX, num_docs, page_window).answer_chain
    if trace and hasattr(chain, "with_config"):
        handler = _new_langfuse_handler()
        if handler:
            return chain.with_config(callbacks=[handler])
    return chain


answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
        inputs.get("page_window", chain_config._PAGE_WINDOW),   
    )
)
