"""Pydantic models for feedback endpoints."""

from __future__ import annotations

from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class Feedback(BaseModel):
    """Model for *POST /feedback* requests."""

    run_id: UUID = Field(..., description="LangSmith run identifier")
    key: str = "user_score"
    score: Union[float, int, bool, None] = None
    feedback_id: Optional[UUID] = None
    comment: Optional[str] = None
    conversation: Optional[list] = None
    documents: Optional[list[str]] = None


class FeedbackUpdate(BaseModel):
    """Model for *PATCH /feedback* requests."""

    feedback_id: Optional[UUID]
    score: Union[float, int, bool, None] | None = None
    comment: Optional[str] = None
