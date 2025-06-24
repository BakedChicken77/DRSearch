from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from typing import List, Any

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

feedback_log: List[Any] = []

@app.post("/chat/stream_log")
async def chat_stream(request: Request):
    body = await request.json()
    user_question = body.get("input", {}).get("question")
    index_name = body.get("input", {}).get("index_name")
    print(f"[Simulator] Received question: {user_question}")
    if index_name:
        print(f"[Simulator] Index requested: {index_name}")
    auth_header = request.headers.get("authorization")
    if auth_header:
        print(f"[Simulator] Authorization header: {auth_header}")

    def event_stream():
        partial1 = "Hello, "
        partial2 = "this is a demo."
        chunk1 = {
            "ops": [
                {"op": "add", "path": "/streamed_output", "value": []},
                {"op": "add", "path": "/streamed_output/0", "value": partial1},
            ],
            "id": "sim-run-123",
            "streamed_output": [partial1],
        }
        yield f"event: data\ndata: {json.dumps(chunk1)}\n\n"
        chunk2 = {
            "ops": [
                {"op": "add", "path": "/streamed_output/1", "value": partial2},
            ],
            "id": "sim-run-123",
            "streamed_output": [partial1, partial2],
        }
        yield f"event: data\ndata: {json.dumps(chunk2)}\n\n"
        yield "event: end\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/index-options")
async def get_index_options():
    index_list = [
        {
            "name": "Demo_Index_1",
            "display_name": "Demo Index 1",
            "example_questions": [
                "What is Demo Index 1 used for?",
                "How to use Demo Index 1?",
            ],
            "initialized": True,
        },
        {
            "name": "Demo_Index_2",
            "display_name": "Demo Index 2",
            "example_questions": [
                "Sample question for index 2?",
                "Another example query?",
            ],
            "initialized": False,
        },
    ]
    return {"result": index_list, "code": 200}


@app.post("/feedback")
async def post_feedback(request: Request):
    feedback_data = await request.json()
    feedback_log.append(feedback_data)
    print(f"[Simulator] Feedback received: {feedback_data}")
    return {"result": "posted feedback successfully", "code": 200}

