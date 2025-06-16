"""
API v1 – mimics original drsearch_backend endpoints.
"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse
from pathlib import Path as FsPath
from ..schema import (
    QueryRequest, QueryResponse,
    FeedbackRequest, FeedbackResponse,
    IndexOptionsResponse, IndexOption,
)
from ...agents.agent import run_agent
from ...config import get_settings
from ...logging import logger

router = APIRouter(prefix="/api/v1")

# -------- /query --------
@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    answer = await run_agent(req.question)
    return QueryResponse(answer=answer)


# -------- /feedback --------
@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest) -> FeedbackResponse:
    # Very simple JSONL logging – extend as needed
    settings = get_settings()
    feedback_path = settings.DATA_DIR / "feedback.log"
    feedback_path.parent.mkdir(exist_ok=True, parents=True)
    feedback_path.write_text(req.model_dump_json() + "\n", encoding="utf-8", append=True)
    logger.info("Stored feedback")
    return FeedbackResponse()


# -------- /index-options --------
@router.get("/index-options", response_model=IndexOptionsResponse)
async def index_options() -> IndexOptionsResponse:
    # Single default index. Update if you support multiple corpora.
    opt = IndexOption(name="default", initialized=True)
    return IndexOptionsResponse(result=[opt])


# -------- /files/{filename} --------
@router.get("/files/{filename}")
async def get_file(filename: str = Path(..., min_length=1)) -> FileResponse:
    # Serve raw source documents stored under DATA_DIR/files
    file_path = FsPath(get_settings().DATA_DIR) / "files" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
