# file: app/chain/cli.py

from __future__ import annotations

import argparse
import logging

from pythonjsonlogger import jsonlogger

from app.core.chain_config import _DEFAULT_INDEX
from app.chain.api import _engine_for

# ─── Logging setup ────────────────────────────────────────────────────────────

_LOG_HANDLER = logging.StreamHandler()
_LOG_HANDLER.setFormatter(
    jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_LOG_HANDLER])
logger = logging.getLogger(__name__)


def _cli() -> None:  # noqa: D401
    """Standalone REPL / one-shot question handler."""
    parser = argparse.ArgumentParser(
        description="Run the RAG/chat chain without the FastAPI server.",
        prog="python -m app.chain.cli",
    )
    parser.add_argument("-q", "--question", help="Ask a single question and exit")
    parser.add_argument(
        "-i",
        "--index-name",
        default=_DEFAULT_INDEX,
        help=f"Weaviate index to query (default: {_DEFAULT_INDEX})",
    )
    opts = parser.parse_args()

    engine = _engine_for(opts.index_name)
    invoke = lambda q, h: engine.answer_chain.invoke(  # noqa: E731
        {"question": q, "chat_history": h, "index_name": opts.index_name}
    )

    # One-shot mode
    if opts.question:
        print(invoke(opts.question, []))
        return

    # Interactive loop
    print(f"Interactive RAG chat (index = '{opts.index_name}'). Type 'exit' to quit.")
    history: list[dict[str, str]] = []
    try:
        while True:
            user_q = input("You: ").strip()
            if user_q.lower() in {"exit", "quit"}:
                break
            if not user_q:
                continue
            ai_resp = invoke(user_q, history)
            print(f"AI: {ai_resp}\n")
            history.append({"human": user_q, "ai": ai_resp})
    except (KeyboardInterrupt, EOFError):
        print("\nExiting. Goodbye!")


if __name__ == "__main__":  # pragma: no cover
    _cli()
