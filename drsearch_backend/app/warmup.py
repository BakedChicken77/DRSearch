from __future__ import annotations

from typing import Dict
import logging

from app.index_options import INDEX_OPTIONS
from app.search_agent.agent import run_agent


class _AgentWrapper:
    async def ainvoke(self, data: dict) -> str:
        history = []
        for item in data.get("chat_history", []):
            history.append(f"User: {item.get('human', '')}")
            history.append(f"Assistant: {item.get('ai', '')}")
        return await run_agent(data["question"], history)


def get_answer_chain(_: str) -> _AgentWrapper:  # pragma: no cover - shim for tests
    return _AgentWrapper()

logger = logging.getLogger(__name__)

# Track whether each index has been successfully warmed up
INDEX_STATUS: Dict[str, bool] = {opt["name"]: False for opt in INDEX_OPTIONS}


async def warm_up_indexes() -> None:
    """Initialise all indexes so first user request is fast."""
    for index_name in INDEX_STATUS.keys():
        try:
            engine = get_answer_chain(index_name)
            await engine.ainvoke({"question": "warmup", "chat_history": []})
            INDEX_STATUS[index_name] = True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Warm-up failed for %s", index_name, exc_info=exc)
            INDEX_STATUS[index_name] = False
