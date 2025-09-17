import asyncio
import json
import random
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
    {
        "name": "TEST_INDEX",
        "display_name": "TEST_INDEX",
        "initialized": True,
        "example_questions": ["Example question 1", "Example question 2"],
    },
    {
        "name": "OTHER_INDEX",
        "display_name": "OTHER_INDEX",
        "initialized": True,
        "example_questions": ["Other question 1", "Other question 2"],
    },
    {"name": "ERROR_500", 
     "display_name": "ERROR_500", 
     "initialized": True,
     "example_questions": ["Example question 1", "Example question 2"],
     },
    {"name": "SLOW_STREAM", 
     "display_name": "SLOW_STREAM", 
     "initialized": True,
     "example_questions": ["Example question 1", "Example question 2"],
     },
    {
        "name": "MALFORMED_SSE",
        "display_name": "MALFORMED_SSE",
        "initialized": True,
        "example_questions": ["Example question 1", "Example question 2"],
    },
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


async def stream_lines(fp: Path, delay: float = 0.001, malformed: bool = False):
    with fp.open() as f:
        for line in f:
            yield line
            if malformed and random.random() < 0.1:
                yield "garbage line\n"
            if line.startswith("event: data"):
                await asyncio.sleep(delay)
    await asyncio.sleep(delay)
    yield "event: end\n\n"


@app.post("/chat/stream_log")
async def chat_stream_log(request: Request):
    global last_request
    last_request = await request.json()
    idx = last_request.get("input", {}).get("index_name")
    if idx == "ERROR_500":
        return JSONResponse({"detail": "backend failure"}, status_code=500)

    trace_fp = get_trace_file(last_request)
    if idx == "SLOW_STREAM":
        delay = float(last_request.get("delay", 0.001))
        return StreamingResponse(
            stream_lines(trace_fp, delay=delay), media_type="text/event-stream"
        )

    malformed = idx == "MALFORMED_SSE"
    return StreamingResponse(
        stream_lines(trace_fp, malformed=malformed),
        media_type="text/event-stream",
    )


@app.get("/last_request")
async def get_last_request():
    return JSONResponse(last_request or {})


@app.get("/index-options")
async def index_options():
    return {"result": INDEX_OPTIONS, "code": 200}
