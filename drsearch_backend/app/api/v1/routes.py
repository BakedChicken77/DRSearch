# file: app/api/routes.py

"""API router composition keeping the *main* module minimal."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any, Dict, AsyncIterator

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse

from ...core.config import Settings, get_settings
from ...auth.middleware import AuthMiddleware  # noqa: F401 – imported for side-effects
from app.auth import jwt  # triggers cache warming on app-start
from app.search_agent.agent import run_agent
from app.models import (
    ChatRequest,
    Feedback,
    FeedbackUpdate,
    IndexOption,
    IndexOptionsResponse,
    StandardResponse,
    TraceRequest,
)
from app.warmup import INDEX_STATUS

feedback_logger = logging.getLogger("feedback")


def _store_feedback(entry: dict) -> None:
    feedback_logger.info("feedback", extra=entry)


logger = logging.getLogger(__name__)

# ---------- auxiliary ----------

BASE_DIR = Path(__file__).resolve().parent
INDEX_OPTIONS_PATH = BASE_DIR / ".." / ".." / "index_options.py"


async def _read_index_options() -> list:  # pragma: no cover – pure I/O
    from importlib import import_module

    mod = import_module("app.index_options")
    return getattr(mod, "INDEX_OPTIONS", [])


# ---------- chat helper functions ----------

async def _call_agent(inputs: dict) -> str:
    """Call the agent with the given inputs and return the response."""
    history = []
    for item in inputs.get("chat_history", []):
        history.append(f"User: {item.get('human', '')}")
        history.append(f"Assistant: {item.get('ai', '')}")
    return await run_agent(inputs["question"], history)


async def _stream_agent_response(inputs: dict) -> AsyncIterator[str]:
    """Stream the agent response as text chunks."""
    # For now, we'll get the full response and yield it
    # In the future, this could be enhanced to stream from the agent directly
    response = await _call_agent(inputs)
    
    # Simulate streaming by yielding chunks
    chunk_size = 50
    for i in range(0, len(response), chunk_size):
        chunk = response[i:i + chunk_size]
        yield chunk
        # Small delay to simulate streaming
        await asyncio.sleep(0.01)


async def _stream_agent_log(inputs: dict) -> AsyncIterator[str]:
    """Stream the agent response with log information in Langserve format."""
    # Get the response
    response = await _call_agent(inputs)
    
    # Format as Langserve stream_log format
    # This mimics the format that Langserve uses for stream_log
    ops = [
        {
            "op": "replace",
            "path": "",
            "value": {
                "logs": {},
                "id": "00000000-0000-0000-0000-000000000000",
                "streamed_output": [],
                "final_output": None
            }
        }
    ]
    
    # Send initial log entry
    yield f"data: {json.dumps(ops[0])}\n\n"
    
    # Stream the response in chunks
    chunk_size = 50
    streamed_output = []
    
    for i in range(0, len(response), chunk_size):
        chunk = response[i:i + chunk_size]
        streamed_output.append(chunk)
        
        # Send streaming chunk
        stream_op = {
            "op": "add",
            "path": "/streamed_output/-",
            "value": chunk
        }
        yield f"data: {json.dumps(stream_op)}\n\n"
        
        # Small delay to simulate streaming
        await asyncio.sleep(0.01)
    
    # Send final output
    final_op = {
        "op": "replace",
        "path": "/final_output",
        "value": response
    }
    yield f"data: {json.dumps(final_op)}\n\n"


# ---------- router factory ----------


def build_router(settings: Settings) -> APIRouter:  # noqa: D401 – factory
    router = APIRouter()

    # ---- /chat endpoints (replacing langserve) ----
    
    @router.post("/chat/invoke")
    async def chat_invoke(request: ChatRequest) -> Dict[str, Any]:
        """Invoke the chat agent with a single request."""
        try:
            inputs = {
                "question": request.question,
                "chat_history": request.chat_history or [],
                "index_name": request.index_name,
                "num_docs_retrieved": request.num_docs_retrieved
            }
            
            response = await _call_agent(inputs)
            
            return {
                "output": response,
                "metadata": {
                    "run_id": "00000000-0000-0000-0000-000000000000",
                    "feedback_tokens": []
                }
            }
        except Exception as exc:
            logger.error("Error in chat invoke", exc_info=exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    @router.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """Stream the chat agent response."""
        try:
            inputs = {
                "question": request.question,
                "chat_history": request.chat_history or [],
                "index_name": request.index_name,
                "num_docs_retrieved": request.num_docs_retrieved
            }
            
            return StreamingResponse(
                _stream_agent_response(inputs),
                media_type="text/plain"
            )
        except Exception as exc:
            logger.error("Error in chat stream", exc_info=exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    @router.post("/chat/stream_log")
    async def chat_stream_log(request: ChatRequest) -> StreamingResponse:
        """Stream the chat agent response with logs in Langserve format."""
        try:
            inputs = {
                "question": request.question,
                "chat_history": request.chat_history or [],
                "index_name": request.index_name,
                "num_docs_retrieved": request.num_docs_retrieved
            }
            
            return StreamingResponse(
                _stream_agent_log(inputs),
                media_type="text/plain",
                headers={"Content-Type": "text/plain; charset=utf-8"}
            )
        except Exception as exc:
            logger.error("Error in chat stream_log", exc_info=exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ---- /index-options
    @router.get("/index-options", response_model=IndexOptionsResponse)
    async def index_options() -> IndexOptionsResponse:  # noqa: D401
        try:
            raw_opts = await _read_index_options()
            opts = [
                IndexOption(**o, initialized=INDEX_STATUS.get(o["name"], False))
                for o in raw_opts
            ]
            return IndexOptionsResponse(result=opts)
        except Exception as exc:  # pragma: no cover – catastrophic
            logger.error("Unable to read index options", exc_info=exc)
            raise HTTPException(
                status_code=500, detail="Unable to read index options"
            ) from exc

    # ---- feedback endpoints -------------------------------------------------
    @router.post("/feedback", status_code=200, response_model=StandardResponse)
    async def create_feedback(body: Feedback) -> StandardResponse:  # noqa: D401
        # TODO: integrate LangSmith client when available
        data = body.model_dump()
        data["thumb"] = "up" if body.score and float(body.score) > 0 else "down"
        _store_feedback(data)
        logger.info("Feedback stored")
        return StandardResponse(result="posted feedback successfully")

    @router.patch("/feedback", status_code=200, response_model=StandardResponse)
    async def patch_feedback(body: FeedbackUpdate) -> StandardResponse:  # noqa: D401
        if body.feedback_id is None:
            raise HTTPException(status_code=400, detail="Missing feedback_id")
        _store_feedback({"patch": body.model_dump()})
        logger.info("Feedback patched")
        return StandardResponse(result="patched feedback successfully")

    # ---- get‑trace (stub) ---------------------------------------------------
    @router.post("/get_trace")
    async def get_trace(
        _: TraceRequest,
    ) -> Response:  # noqa: D401 – not yet implemented
        raise HTTPException(status_code=501, detail="Trace sharing not implemented")

    # ---- file download proxy -----------------------------------------------
    @router.get("/files/{file_path:path}")
    async def read_file(file_path: str) -> FileResponse:  # noqa: D401
        decoded = urllib.parse.unquote(file_path)
        unc_path = os.path.normpath(os.path.join(BASE_DIR, decoded))  # Normalize path

        if not unc_path.startswith(str(BASE_DIR)):
            logger.warning(
                "Attempted access to unauthorized path", extra={"path": unc_path}
            )
            raise HTTPException(
                status_code=403, detail="Access to this file is forbidden"
            )

        if not os.path.exists(unc_path):
            logger.info("File not found", extra={"path": unc_path})
            raise HTTPException(status_code=404, detail="File not found")

        media_type = (
            "application/pdf"
            if unc_path.lower().endswith(".pdf")
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        return FileResponse(
            path=unc_path,
            media_type=media_type,
            filename=os.path.basename(unc_path),
            headers={
                "Content-Disposition": f'inline; filename="{os.path.basename(unc_path)}"'
            },
        )

    return router
