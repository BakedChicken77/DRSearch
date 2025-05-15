# file: app/api/schemas.py


"""Pydantic request / response models used by the API layer."""

from __future__ import annotations

from typing import Optional, Union, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


# file: app/api/v1/schemas.py

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """Request body consumed by FastAPI & CLI."""

    question: str = Field(..., description="User query in natural language")
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of prior messages, each { 'human': str, 'ai': str }"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Optional override for the Weaviate index name"
    )


class Feedback(BaseModel):
    """Request body for *POST /feedback* endpoint."""

    run_id: UUID = Field(..., description="LangSmith run identifier")
    key: str = "user_score"
    score: Union[float, int, bool, None] = None
    feedback_id: Optional[UUID] = None
    comment: Optional[str] = None


class FeedbackUpdate(BaseModel):
    """Request body for *PATCH /feedback* endpoint."""

    feedback_id: Optional[UUID]
    score: Union[float, int, bool, None] | None = None
    comment: Optional[str] = None


class TraceRequest(BaseModel):
    """Request body for *POST /get_trace* endpoint."""

    run_id: UUID
