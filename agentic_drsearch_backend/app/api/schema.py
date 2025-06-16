"""Shared Pydantic schemas used by API routes."""

from typing import List, Optional
from pydantic import BaseModel, Field


# === /query ===
class QueryRequest(BaseModel):
    question: str = Field(..., example="What is the maximum duty cycle?")

class QueryResponse(BaseModel):
    answer: str


# === /feedback ===
class FeedbackRequest(BaseModel):
    run_id: Optional[str] = None
    score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    citations: Optional[List[str]] = None

class FeedbackResponse(BaseModel):
    status: str = "success"


# === /index-options ===
class IndexOption(BaseModel):
    name: str
    initialized: bool

class IndexOptionsResponse(BaseModel):
    result: List[IndexOption]
