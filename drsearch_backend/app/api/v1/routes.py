# file: app/api/routes.py

"""API router composition keeping the *main* module minimal."""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path
from typing import Callable, List

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from langserve import add_routes

from ...core.config import Settings, get_settings
from ...auth.middleware import AuthMiddleware  # noqa: F401 – imported for side-effects
from app.auth import jwt  # triggers cache warming on app-start
from app.chain.api import answer_chain 
from .schemas import Feedback, FeedbackUpdate, TraceRequest, ChatRequest
from ...core.logging import logging

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
    add_routes(
        router,
        answer_chain,
        path="/chat",
        input_type=ChatRequest,
        config_keys=["metadata"],
    )

    # ---- /index-options
    @router.get("/index-options")  # noqa: D401 – inline route
    async def index_options() -> dict:  # noqa: D401
        try:
            return {"code": 200, "result": await _read_index_options()}
        except Exception as exc:  # pragma: no cover – catastrophic
            logger.error("Unable to read index options", exc_info=exc)
            raise HTTPException(status_code=500, detail="Unable to read index options") from exc

    # ---- feedback endpoints -------------------------------------------------
    @router.post("/feedback", status_code=200)
    async def create_feedback(body: Feedback) -> dict:  # noqa: D401
        # TODO: integrate LangSmith client when available
        logger.info("Feedback received", extra=body.dict())
        return {"result": "posted feedback successfully", "code": 200}

    @router.patch("/feedback", status_code=200)
    async def patch_feedback(body: FeedbackUpdate) -> dict:  # noqa: D401
        if body.feedback_id is None:
            raise HTTPException(status_code=400, detail="Missing feedback_id")
        logger.info("Feedback patched", extra=body.dict())
        return {"result": "patched feedback successfully", "code": 200}

    # ---- get‑trace (stub) ---------------------------------------------------
    @router.post("/get_trace")
    async def get_trace(_: TraceRequest) -> Response:  # noqa: D401 – not yet implemented
        raise HTTPException(status_code=501, detail="Trace sharing not implemented")

    # ---- file download proxy -----------------------------------------------
    @router.get("/files/{file_path:path}")
    async def read_file(file_path: str) -> FileResponse:  # noqa: D401
        decoded = urllib.parse.unquote(file_path)
        unc_path = decoded.replace("/", "\\")  # UNC path on Windows share

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
            headers={"Content-Disposition": f'inline; filename="{os.path.basename(unc_path)}"'},
        )

    return router
