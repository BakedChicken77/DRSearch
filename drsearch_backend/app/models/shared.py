"""Shared Pydantic models used across the API."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """Generic API response wrapper."""

    result: Any
    code: int = Field(200, description="Application level status code")


class IndexOption(BaseModel):
    """Single index option returned by `/index-options`."""

    name: str
    display_name: Optional[str] = None
    example_questions: Optional[List[str]] = None


class IndexOptionsResponse(BaseModel):
    """Response model for `/index-options`."""

    result: List[IndexOption]
    code: int = Field(200, description="Application level status code")

