# file: app/api/routes.py

"""API router composition keeping the *main* module minimal."""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from langserve import add_routes

from ...core.config import Settings, get_settings
from ...auth.middleware import AuthMiddleware  # noqa: F401 – imported for side-effects
from app.auth import jwt  # triggers cache warming on app-start
from app.chain.api import answer_chain
from langchain_core.runnables import RunnableLambda
from app.search_agent.agent import run_agent, run_agent_streamed
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
import json

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


# ---------- router factory ----------


def build_router(settings: Settings) -> APIRouter:  # noqa: D401 – factory
    router = APIRouter()

    # ---- /chat  (langserve wires up streaming handlers etc.)
    async def _invoke_agent(inputs: dict) -> str:
        history = []
        for item in inputs.get("chat_history", []):
            history.append(f"User: {item.get('human', '')}")
            history.append(f"Assistant: {item.get('ai', '')}")
        return await run_agent(inputs["question"], history)

    agent_chain = RunnableLambda(_invoke_agent)

    add_routes(
        router,
        agent_chain,
        path="/chat",
        input_type=ChatRequest,
        config_keys=["metadata"],
        playground_type="chat",
    )

    @router.post("/chat", response_model=None)
    async def _call_agent(body: ChatRequest) -> StreamingResponse:
        history = []
        for item in body.chat_history or []:
            history.append(f"User: {item.get('human', '')}")
            history.append(f"Assistant: {item.get('ai', '')}")

        async def event_stream() -> AsyncIterator[str]:
            stream = await run_agent_streamed(body.question, history)
            async for event in stream:
                data = json.dumps(event, default=str)
                yield f"event: {event.type}\n" f"data: {data}\n\n"
            yield "event: end\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

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
        data = body.dict()
        data["thumb"] = "up" if body.score and float(body.score) > 0 else "down"
        _store_feedback(data)
        logger.info("Feedback stored")
        return StandardResponse(result="posted feedback successfully")

    @router.patch("/feedback", status_code=200, response_model=StandardResponse)
    async def patch_feedback(body: FeedbackUpdate) -> StandardResponse:  # noqa: D401
        if body.feedback_id is None:
            raise HTTPException(status_code=400, detail="Missing feedback_id")
        _store_feedback({"patch": body.dict()})
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
