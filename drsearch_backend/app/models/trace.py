"""Pydantic model for trace-related requests."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TraceRequest(BaseModel):
    """Model for *POST /get_trace* requests."""

    run_id: UUID
