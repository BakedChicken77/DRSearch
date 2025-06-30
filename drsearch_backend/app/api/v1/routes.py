# file: app/api/routes.py

"""API router composition keeping the *main* module minimal."""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path
import asyncio
import json

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import FileResponse, StreamingResponse

from ...core.config import Settings
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


# ---------- router factory ----------


def build_router(settings: Settings) -> APIRouter:  # noqa: D401 – factory
    router = APIRouter()

    # ---- /chat ------------------------------------------------------------

    def _build_history(chat_history: list[dict[str, str]] | None) -> list[str]:
        """Convert frontend style history records into a simple \n-separated list
        expected by *run_agent*.
        """

        if not chat_history:
            return []

        history: list[str] = []
        for item in chat_history:
            history.append(f"User: {item.get('human', '')}")
            history.append(f"Assistant: {item.get('ai', '')}")
        return history

    @router.post("/chat", response_model=StandardResponse)
    async def chat(body: ChatRequest) -> StandardResponse:  # noqa: D401 – main chat
        """Synchronous chat endpoint returning a single response string."""

        answer = await run_agent(body.question, _build_history(body.chat_history))
        return StandardResponse(result=answer)

    # ---- /chat/stream_log --------------------------------------------------

    @router.post("/chat/stream_log")
    async def chat_stream_log(request: Request):  # noqa: D401 – SSE stream
        """Stream chat response as Server-Sent Events compatible with the
        existing frontend.  The request payload follows LangServe's schema:

        {
          "input": { ...ChatRequest fields... },
          "config": { ... },            # ignored
          "include_names": [ ... ]      # ignored
        }
        """

        try:
            payload = await request.json()
        except Exception as exc:  # pragma: no cover – malformed JSON
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

        try:
            chat_input = payload.get("input", {})
            chat_req = ChatRequest(**chat_input)
        except Exception as exc:  # pragma: no cover – validation errors
            raise HTTPException(status_code=422, detail="Invalid chat input") from exc

        answer = await run_agent(
            chat_req.question, _build_history(chat_req.chat_history)
        )

        async def _event_generator():
            """Yield SSE formatted patches building the streamed output."""

            # First patch initialises the array so subsequent *-/add* ops succeed
            if not answer:
                # No answer – just terminate stream
                yield "event: end\n\n"
                return

            # Initialise streamed_output with the first character
            first_char, rest = answer[0], answer[1:]
            init_patch = {"ops": [{"op": "add", "path": "/streamed_output", "value": [first_char]}]}
            yield f"event: data\ndata: {json.dumps(init_patch)}\n\n"

            # subsequent characters are appended one-by-one
            for ch in rest:
                patch = {
                    "ops": [
                        {
                            "op": "add",
                            "path": "/streamed_output/-",
                            "value": ch,
                        }
                    ]
                }
                yield f"event: data\ndata: {json.dumps(patch)}\n\n"
                # Short sleep to ensure cooperative multitasking and allow
                # the client to process chunks progressively.
                await asyncio.sleep(0)  # pragma: no cover

            # Signal completion
            yield "event: end\n\n"

        return StreamingResponse(_event_generator(), media_type="text/event-stream")

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
