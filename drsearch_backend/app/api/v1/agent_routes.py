from __future__ import annotations

from fastapi import APIRouter
from langserve import add_routes

from app.agent.rag_agent import agent_chain
from app.models import ChatRequest


def build_agent_router() -> APIRouter:
    router = APIRouter()
    add_routes(
        router,
        agent_chain,
        path="/agent-chat",
        input_type=ChatRequest,
        config_keys=["metadata"],
        playground_type="chat",
    )
    return router
