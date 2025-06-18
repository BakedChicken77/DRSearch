"""Pydantic models for chat functionality."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.chain_config import _NUMBER_OF_DOCS_RETRIEVED


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

    num_docs_retrieved: int = Field(
        default=_NUMBER_OF_DOCS_RETRIEVED,
        ge=1,
        le=5,
        description="How many documents to retrieve for each query",
    )
