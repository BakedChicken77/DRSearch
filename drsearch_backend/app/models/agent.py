from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AgentOutput(BaseModel):
    """Generic wrapper for agent responses."""

    output: Any
