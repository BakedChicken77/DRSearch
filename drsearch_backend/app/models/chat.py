"""Pydantic models for chat functionality."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Input model for chat requests."""

    question: str = Field(..., description="User query in natural language")
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of prior messages, each {'human': str, 'ai': str}",
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Optional override for the Weaviate index name",
    )

