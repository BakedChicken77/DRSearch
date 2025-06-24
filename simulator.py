from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio, json, uuid
from typing import List, Dict, Any

app = FastAPI(title="DRSearch Backend Simulator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

feedback_log: List[Dict[str, Any]] = []

# ----------------------------- index options -----------------------------
@app.get("/index-options")
async def get_index_options() -> Dict[str, Any]:
    """Return mock index metadata (matches IndexOptionsResponse)."""
    return {
        "result": [
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
        ],
        "code": 200,
    }

# ------------------------------- feedback -------------------------------
@app.post("/feedback")
async def post_feedback(request: Request) -> Dict[str, Any]:
    """Accept feedback payload and keep it in memory for the session."""
    payload = await request.json()
    feedback_log.append(payload)
    print(f"[Simulator] Feedback received: {payload}")
    return {"result": "posted feedback successfully", "code": 200}

# ---------------------------- streaming chat ----------------------------
@app.post("/chat/stream_log")
async def chat_stream(request: Request) -> StreamingResponse:
    """Simulate LangServe /chat streaming via SSE."""
    body = await request.json()
    print(f"[Simulator] Received chat payload: {body}")

    user_question = body.get("input", {}).get("question")
    index_name = body.get("input", {}).get("index_name")
    print(f"[Simulator] Question: {user_question} | Index: {index_name}")

    run_id = str(uuid.uuid4())
    partials = ["Hello, ", "this is a demo."]

    async def event_stream():
        streamed: List[str] = []
        for i, chunk in enumerate(partials):
            streamed.append(chunk)
            payload = {
                "ops": (
                    [{"op": "add", "path": "/streamed_output", "value": []}]
                    if i == 0
                    else []
                )
                + [
                    {"op": "add", "path": f"/streamed_output/{i}", "value": chunk},
                ],
                "id": run_id,
                "streamed_output": streamed,
            }
            yield f"event: data\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.2)
        yield "event: end\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ------------------------------- run uvicorn ------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("simulator:app", host="0.0.0.0", port=8011, reload=True)
