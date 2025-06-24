# Building a FastAPI Backend API Simulator for DRSearch

In this guide, we will create a **standalone FastAPI app** that simulates key endpoints of the `drsearch_backend`. This simulator will mimic the real backend’s behavior so the `drsearch_frontend` can be tested in isolation. We will implement **only the required endpoints** and use known response patterns from the real backend. The endpoints to simulate are:

* **`POST /chat/stream_log`** – provides chunked server-sent events (SSE) to stream chatbot responses
* **`GET /index-options`** – returns a list of index metadata (for dropdown options)
* **`POST /feedback`** – accepts user feedback data and logs it

No authentication or authorization checks will be enforced in our simulator. The frontend may still send headers like `Authorization` or `X-Index-Name`, but our simulator will ignore them (or simply log them) per requirements. We’ll focus on returning the correct **payload structure**, **status codes**, and **streaming behavior** expected by the frontend.

## 1. Analyze the Real Backend Endpoints

Before coding, let’s understand how the real `drsearch_backend` works for these endpoints. This will ensure our simulator’s responses match the frontend’s expectations.

### 1.1 `POST /chat/stream_log` – Streaming Chat Responses via SSE

In the actual backend, this endpoint streams the chatbot’s answer as a sequence of events. The frontend initiates a chat query by sending a POST request with JSON including the user’s question, chat history, index name, etc., and sets the `Accept: text/event-stream` header. The backend responds with a stream of text events rather than a single JSON response.

**Expected Request Format:** The frontend sends a JSON payload like:

```json
{
  "input": {
    "question": "User's question text",
    "chat_history": [ ... ],       // array of past Q&A (if any)
    "index_name": "SelectedIndex", // which knowledge index to use
    "num_docs_retrieved": 3       // number of docs to retrieve
  },
  "config": { 
    "metadata": { "conversation_id": "<uuid>" } 
  },
  "include_names": ["FindDocs"]   // instructs which chain logs to include
}
```

This matches what the front end constructs in `ChatWindow.tsx` before calling the API. The simulator should accept this JSON (we don’t need to fully validate its content, but we can parse or log it).

**Streaming Response Structure:** The backend uses **Server-Sent Events** to send back the answer incrementally. Each SSE message is a text block beginning with an event name, followed by data. In the real implementation, the Node/Edge route produces events named `"data"` for each chunk and an `"end"` event to signal completion. For example, the server might send:

```
event: data
data: {"ops":[...], "id": "run123", "streamed_output": ["Hello, "]}

event: data
data: {"ops":[...], "id": "run123", "streamed_output": ["Hello, ", "world!"]}

event: end
```

Each `event: data` chunk contains a JSON object (here shown pretty-printed) with fields like:

* **`streamed_output`** – an array of text segments received so far. The frontend concatenates this to form the answer.
* **`ops`** – a list of JSON-Patch operations representing changes (used by the frontend to incrementally update the response state).
* **`id`** – an identifier for the run/response (optional, used for logging or reference).

The frontend listens for these SSE events. On each `data` event, it parses the JSON, applies `chunk.ops` as patches to a persistent `streamedResponse` object, and updates the chat UI with the cumulative text. When an `event: end` is received, the frontend knows the answer is complete and stops the loading state.

✅ **Summary of `/chat/stream_log`:** The simulator must return an HTTP **200 OK** with a continuous **`text/event-stream`** response. We will emit multiple `data` events (with JSON payloads) followed by a final `end` event, exactly as the real backend does. This ensures the frontend’s SSE handler (using `fetchEventSource`) can process the answer in chunks and finalize on the `end` event.

### 1.2 `GET /index-options` – Index Metadata List

This endpoint provides the frontend with a list of available document indexes and their metadata, used to populate the “Select Document Index” dropdown. In `drsearch_backend`, the response is modeled by `IndexOptionsResponse`, containing a list of `IndexOption` objects and an application-level status code.

Each **IndexOption** includes:

* `name` – internal index identifier (used in queries)
* `display_name` – human-friendly name for UI
* `example_questions` – a few sample questions (strings) related to that index
* `initialized` – a boolean indicating if the index is warmed up and ready (true means available, false means not yet loaded or still initializing).

In the real backend, these options are defined in a central list. For example, `app/index_options.py` defines several indexes with their name, display\_name, and example questions. When `/index-options` is called, the backend reads this list and adds an `initialized` flag for each entry (using a global status tracker). It then returns a JSON with `result` as the list of index option objects and `code: 200`.

**Example Real Response:**

```json
{
  "result": [
    {
      "name": "JACSKE_Program",
      "display_name": "JACSKE Program",
      "example_questions": [
        "What should the output power of the TR Module be?",
        "Where in the Receiver‑Transmitter is the XMIT Trigger generated?",
        "... (more questions) ..."
      ],
      "initialized": true
    },
    {
      "name": "SEPs_F_T_C_W_A_V_Summaries",
      "display_name": "SEPS",
      "example_questions": [
        "How do I fill out my timesheet?",
        "How do I request PTO?",
        "..."],
      "initialized": false
    }
    // ... more indexes ...
  ],
  "code": 200
}
```

The frontend expects exactly this structure. In fact, the frontend utility `fetchIndexOptions` checks that `response.code === 200` and that `response.result` is an array. It then uses `response.result` to populate the dropdown of indexes. Any index with `initialized: false` will be shown disabled (greyed out) in the select list.

✅ **Summary of `/index-options`:** Our simulator will return a **200 OK** JSON with a **`result`** list of index objects. We can use a few representative index entries (e.g., from actual config or made-up ones) and mark some as initialized. The exact names aren’t crucial, but the fields and types must match the real response format.

### 1.3 `POST /feedback` – Logging Feedback

The feedback endpoint allows the frontend to send user feedback on answers (like upvote/downvote or comments). In the real backend, the request is defined by a Pydantic model `Feedback`, which includes fields such as:

* `run_id` (UUID of the Q\&A session or LLM run)
* `score` (numeric or boolean indicating user rating, e.g. 1 or true for upvote, 0 or false for downvote)
* `comment` (optional text comment)
* `feedback_id` (optional UUID, sometimes used for updates)
* `conversation` and `documents` (optional, additional context).

When the backend receives a POST to `/feedback`, it converts the payload to a dict, adds a `"thumb"` field internally (e.g. “up” or “down” based on the score > 0) and logs it. The response is a simple confirmation message in a `StandardResponse` object. The response JSON looks like:

```json
{ "result": "posted feedback successfully", "code": 200 }
```

There is also a PATCH `/feedback` in the real API for updating feedback, but **we will only implement the POST** variant as required.

✅ **Summary of `/feedback`:** The simulator should accept a JSON body (we won’t enforce all fields strictly, but we expect at least a `run_id` and maybe a `score`). It will then **log or print** the feedback for inspection (in-memory logging is sufficient) and return a **200 OK** with a JSON message confirming receipt (just like the real backend returns). No auth or API key checks required.

---

**No Authentication Needed:** In all the above, authentication is disabled or not required for our simulator. The real system might accept a bearer token in the `Authorization` header (the frontend passes it if enabled), but our simulator will neither validate nor require any token. We can simply ignore these headers or print them for debugging. The focus is on correct endpoint behavior and data format.

With understanding in place, let’s move on to building the simulator.

## 2. Setting Up the FastAPI Simulator

First, ensure you have **FastAPI** and an ASGI server (like **Uvicorn**) installed in your Python environment:

```bash
pip install fastapi uvicorn
```

Create a new Python file for the simulator (e.g., `simulator.py`). In this file, we will:

* Initialize a FastAPI app.
* (Optional) Enable CORS, so the frontend (possibly running on a different origin like `http://localhost:3000`) can call our simulator without issues.
* Define the three endpoints: `POST /chat/stream_log`, `GET /index-options`, and `POST /feedback`.

#### Enabling CORS (Optional but Recommended)

If your frontend is served from a different origin/port than this simulator, add CORS middleware to avoid cross-origin errors. For simplicity, we’ll allow all origins. Add this before defining routes:

```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify frontend URL like ["http://localhost:3000"]
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This matches the real backend’s behavior which permits the configured origins for all methods and headers.

## 3. Implementing the `/chat/stream_log` SSE Endpoint

Streaming responses in FastAPI can be done using `StreamingResponse`. We’ll create a generator that yields SSE-formatted strings. Each yield corresponds to a chunk of the response.

**Key steps for SSE:**

* **Content Type:** Use `text/event-stream` as the media type in the response. This keeps the connection open and tells the client to expect a stream.
* **Event Formatting:** Each message must end with a double newline (`\n\n`). We also prefix custom event names if needed. In our case, we use `event: data` for answer chunks and `event: end` for the final message.
* **Flush Behavior:** FastAPI/Starlette will flush each yielded string immediately. For local testing, no extra flush is needed, but avoid large delays in the generator loop unless simulating latency.

Let’s write the route handler. We can simulate a simple conversation: the assistant will respond with a fixed answer (split into a couple of chunks) regardless of question. Feel free to adjust the content to something relevant for your app.

```python
from fastapi import Request
from fastapi.responses import StreamingResponse
import json

@app.post("/chat/stream_log")
async def chat_stream(request: Request):
    # Parse the incoming JSON (though we might not use it for static response)
    body = await request.json()
    user_question = body.get("input", {}).get("question")  # just for logging
    
    # We can log the question and any headers for debugging
    print(f"[Simulator] Received question: {user_question}")
    auth_header = request.headers.get("authorization")
    if auth_header:
        print(f"[Simulator] Authorization header received: {auth_header}")
    index_name = body.get("input", {}).get("index_name")
    if index_name:
        print(f"[Simulator] Index requested: {index_name}")
    
    # Define a generator to yield SSE events
    def event_stream():
        # Example partial answer chunks (you can use realistic content here)
        partial1 = "Hello, "            # first part of answer
        partial2 = "this is a demo."    # second part of answer
        
        # Construct first SSE data chunk as a JSON patch
        chunk1 = {
            "ops": [
                {"op": "add", "path": "/streamed_output", "value": []},
                {"op": "add", "path": "/streamed_output/0", "value": partial1}
            ],
            "id": "sim-run-123",               # a made-up run ID
            "streamed_output": [partial1]      # current accumulated text
        }
        yield f"event: data\ndata: {json.dumps(chunk1)}\n\n"
        
        # Construct second SSE data chunk (appending the second part)
        chunk2 = {
            "ops": [
                {"op": "add", "path": "/streamed_output/1", "value": partial2}
            ],
            "id": "sim-run-123",
            "streamed_output": [partial1, partial2]
        }
        yield f"event: data\ndata: {json.dumps(chunk2)}\n\n"
        
        # Send the end-of-stream event
        yield "event: end\n\n"
    
    # Return a streaming response with the generator
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Let’s break down what we did:

* We read the request JSON with `await request.json()`. This gives us the input payload if we need to use it (our example just logs the question and index).
* The `event_stream()` inner function is a **normal generator** (not async). It yields preformed SSE strings:

  * The first yield is an `event: data` with a JSON payload. We included an `"ops"` list to mimic JSON patch operations and a `"streamed_output"` array containing the first segment. This follows the structure the real backend sends (the frontend will apply the patch and render "Hello, " in the chat).
  * The second yield is another `event: data` with the next part of the answer. Its patch adds a new element to the `streamed_output` array, now containing both segments (so the combined text is "Hello, this is a demo."). The frontend will update the message to the full sentence.
  * Finally, we yield an `event: end` with no data. The double newline after each message is critical to indicate the end of an SSE event frame.
* We wrap the generator in `StreamingResponse` with `media_type="text/event-stream"`. FastAPI will stream each yielded string to the client as an SSE packet. The connection will close automatically after the generator is exhausted (after the end event).

This implementation ensures the frontend’s SSE handler receives exactly what it expects. In our example, the answer is hardcoded, but you could programmatically generate different answers or use stored logs of actual responses for realism. The main point is to preserve the **structure** (event names and JSON fields) of the real stream. The real system uses a similar loop to send `event: data` chunks and then an `event: end`.

**Testing the SSE:** Once running, you can test this endpoint with a tool like `curl` to see the streamed output. For example:

```bash
curl -X POST http://localhost:8000/chat/stream_log -H "Accept: text/event-stream" -H "Content-Type: application/json" -d '{"input": {"question": "test?", "index_name": "SomeIndex"}}'
```

You should see the `event: data` and `event: end` messages arriving in sequence. In the browser, the frontend will process them and display the combined answer incrementally.

### Handling Errors (Optional)

For robustness, you might simulate error conditions. For instance, if the request JSON is malformed or missing required fields, you could return an HTTP 400 error. Alternatively, you might simulate a backend exception by streaming an error message and then ending. However, the simplest approach is to always stream a successful answer for testing. The frontend’s error handling (e.g., network failure or non-200 status) can be tested by intentionally returning an error status code in certain scenarios, but that’s optional.

## 4. Implementing the `/index-options` Endpoint

The index options endpoint is straightforward. We will return a JSON object with a **`result`** key containing a list of index metadata, and a **`code`** key set to 200. We can hardcode some mock index entries, ideally resembling those in the real system.

Let’s add the route:

```python
@app.get("/index-options")
async def get_index_options():
    # Define some mock index entries
    index_list = [
        {
            "name": "Demo_Index_1",
            "display_name": "Demo Index 1",
            "example_questions": [
                "What is Demo Index 1 used for?",
                "How to use Demo Index 1?"
            ],
            "initialized": True   # this index is ready to use
        },
        {
            "name": "Demo_Index_2",
            "display_name": "Demo Index 2",
            "example_questions": [
                "Sample question for index 2?",
                "Another example query?"
            ],
            "initialized": False  # simulate an index not yet initialized
        }
    ]
    response = { "result": index_list, "code": 200 }
    return response
```

A few notes:

* We created two example indexes. You can include more or use the actual index names from your `index_options.py` (e.g. "JACSKE\_Program", "SEPS", etc.) for realism. The structure should match the `IndexOption` model fields.
* One index has `initialized: True` (meaning the frontend can select it), and the other is `False` (will appear disabled). This covers both states the UI might handle.
* We return a simple Python dict. FastAPI will automatically convert it to JSON. The `code: 200` is included to mimic the `IndexOptionsResponse` model which always carries a code field.

When the frontend calls this endpoint (via `fetchIndexOptions`), it will receive our mock data and proceed without error as long as the format is correct. If needed, you can also log that the endpoint was hit, or print the fact that you returned options.

## 5. Implementing the `/feedback` Endpoint

Finally, we implement the feedback collection endpoint. We will accept a POST request with a JSON body containing feedback details. The simulator will not verify the content rigorously; it will simply log the feedback and return a success message.

Add the route:

```python
@app.post("/feedback")
async def post_feedback(request: Request):
    feedback_data = await request.json()
    # Log the feedback in-memory (print to console or store in list)
    print(f"[Simulator] Feedback received: {feedback_data}")
    # We could also store it in a global list for later inspection if needed:
    # feedback_log.append(feedback_data)
    
    # Return a success response similar to StandardResponse
    return { "result": "posted feedback successfully", "code": 200 }
```

Points to note:

* We use `Request` to get the raw JSON. Alternatively, we could define a Pydantic model for Feedback to enforce certain fields (like `run_id: UUID`, etc.), but that’s unnecessary for simulation. Accept any JSON and treat it as feedback.
* We log the received data. This could help verify in tests that the frontend is sending the expected payload. (The real backend uses a logger for this purpose.)
* We return a JSON with the exact success message and code the frontend expects. The string `"posted feedback successfully"` matches the real backend’s response for POST feedback.
* We do not implement the PATCH /feedback (update) since it’s out of scope. If your frontend might call it, you could add a similar stub for completeness (e.g., check if `feedback_id` is provided, else return 400, and then return a `"patched feedback successfully"` result). But the prompt only asked for the POST endpoint.

Now the core endpoints are ready.

## 6. Running and Using the Simulator

Start the FastAPI app using Uvicorn (or Hypercorn, etc.). For example:

```bash
uvicorn simulator:app --reload --port 8000
```

This assumes your file is named `simulator.py` and you want to run on port 8000. The `--reload` is handy during development to auto-restart on code changes.

**Configure the Frontend:** Ensure that the frontend is pointing to this simulator’s base URL. In the DRSearch frontend, the base API URL is defined by `apiBaseUrl` (often from an environment variable). You might set `NEXT_PUBLIC_API_BASE_URL` to `http://localhost:8000` (if using Next.js env config), or directly adjust the constant in `app/utils/constants.ts` if it’s hardcoded. The goal is that `fetchEventSource` and other fetch calls use the simulator’s address. For example, in development, you might have:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

so that `apiBaseUrl` picks it up.

**Test the Workflow:** With the simulator running and frontend configured:

* Load the front-end application. The index dropdown should populate via our `/index-options` endpoint. You should see “Demo Index 1” and “Demo Index 2” (with the latter disabled). This confirms our GET endpoint is working.
* Select **Demo Index 1** and ask a question in the chat. The frontend will POST to `/chat/stream_log`. Our simulator will log the request, then stream back the hardcoded answer in two chunks. On the UI, you should see the answer appear gradually (“Hello, ” then “Hello, this is a demo.”).
* The chat history should update and the loading spinner should stop once the `end` event is received. This mimics a complete cycle with streaming.
* Try the feedback: after getting an answer, the frontend might offer a feedback option (thumbs up/down). If it posts to `/feedback`, our simulator will print the feedback JSON and return the success message. No errors should occur on the frontend, as it expects a 200 code and our response provides it.

**Inspect Logs:** All our print statements (for question, auth header, feedback, etc.) will appear in the console running the simulator. This is useful to verify what data the frontend is sending. For example, you’ll see the exact JSON of feedback submissions, which can confirm that things like `run_id` and `score` are being passed.

## 7. Extend as Needed (Optional Enhancements)

We have a basic but functional simulator. Depending on testing needs, you can enhance it:

* **Dynamic Responses:** Instead of fixed answer chunks, you could base the answer on the question (e.g., simple rule-based responses or a small AI model). Ensure to still stream the output in chunks. For example, for certain keywords in the question, return a particular fake answer.
* **Multiple Chunks:** You can break the answer into more than two chunks to better simulate real streaming. Just yield additional `event: data` events with smaller segments.
* **Error Simulation:** Add conditional logic to test frontend error handling. For instance, if `input.index_name` is `"BadIndex"`, respond with an HTTP 500 or a special SSE event indicating an error.
* **Feedback Storage:** Maintain a list of feedback entries in memory and perhaps add a `GET /feedback` route to fetch them for debugging. This isn’t needed by the frontend, but can help during testing to see what was recorded.

Each extension should be done carefully to still respect the frontend contract (e.g., always end SSE with `event: end`, always include `code` in JSON responses).
