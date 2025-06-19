# file: app/chain/history.py

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage


class HistorySerializer:
    """Converts chat history dicts into langchain Message objects."""

    def __call__(self, request_dict: Dict[str, Any]) -> List[AIMessage | HumanMessage]:
        """Serialize raw history into LangChain Message objects."""
        history_raw = request_dict.get("chat_history") or []
        messages: List[AIMessage | HumanMessage] = []

        for item in history_raw:
            if "human" in item:
                messages.append(HumanMessage(content=item["human"]))
            if "ai" in item:
                messages.append(AIMessage(content=item["ai"]))

        return messages
