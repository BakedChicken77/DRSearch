# file: app/chain/models.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.pydantic_v1 import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body consumed by CLI and FastAPI layers."""

    question: str = Field(..., description="User query in natural language")
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of prior messages, each {'human': str, 'ai': str}"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Optional override for the Weaviate index name"
    )