import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pathlib import Path
import json

app = FastAPI(title="DRSearch Trace-Replay Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRACES = {
    "trace1": Path(__file__).parent / "traces" / "trace1.sse",
    "trace2": Path(__file__).parent / "traces" / "trace2.sse",
    "trace3": Path(__file__).parent / "traces" / "trace3.sse",
}

last_request: dict | None = None

@app.post("/chat/stream_log")
async def chat_stream_log(request: Request):
    global last_request
    body = await request.json()
    last_request = body
    inp = body.get("input", {})
    idx = inp.get("index_name")
    num = inp.get("num_docs_retrieved")
    if idx == "TEST_INDEX" and num == 2:
        trace_path = TRACES["trace1"]
    elif idx == "TEST_INDEX" and num == 1:
        trace_path = TRACES["trace2"]
    else:
        trace_path = TRACES["trace3"]

    async def event_generator():
        with open(trace_path, "r") as f:
            for line in f:
                yield line
                if line.startswith("event: data"):
                    await asyncio.sleep(0.01)
        await asyncio.sleep(0.01)
        yield "event: end\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/last_request")
async def get_last_request():
    return JSONResponse(last_request or {})
