import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(title="DRSearch Trace-Replay Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRACES_DIR = Path(__file__).resolve().parent / "traces"
last_request: dict | None = None

INDEX_OPTIONS = [
    {"name": "TEST_INDEX", "display_name": "TEST_INDEX", "initialized": True},
    {"name": "OTHER_INDEX", "display_name": "OTHER_INDEX", "initialized": True},
]


def get_trace_file(body: dict) -> Path:
    inp = body.get("input", {})
    idx = inp.get("index_name")
    num = inp.get("num_docs_retrieved")
    if idx == "TEST_INDEX" and num == 2:
        name = "trace1.sse"
    elif idx == "TEST_INDEX" and num == 1:
        name = "trace2.sse"
    else:
        name = "trace3.sse"
    return TRACES_DIR / name


async def stream_lines(fp: Path):
    with fp.open() as f:
        for line in f:
            yield line
            if line.startswith("event: data"):
                await asyncio.sleep(0.01)
    await asyncio.sleep(0.01)
    yield "event: end\n\n"


@app.post("/chat/stream_log")
async def chat_stream_log(request: Request):
    global last_request
    last_request = await request.json()
    trace_fp = get_trace_file(last_request)
    return StreamingResponse(stream_lines(trace_fp), media_type="text/event-stream")


@app.get("/last_request")
async def get_last_request():
    return JSONResponse(last_request or {})


@app.get("/index-options")
async def index_options():
    return {"result": INDEX_OPTIONS, "code": 200}
