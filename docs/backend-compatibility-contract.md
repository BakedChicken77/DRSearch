# DRSearch Backend Compatibility Contract

## 1. Purpose

This document defines the **actual backend API contract** that the DRSearch frontend depends on. It is reverse-engineered from the frontend source code, validated against the Python backend implementation, and corroborated by test fixtures and SSE trace recordings.

The intended audience is engineers implementing a compatibility layer or adapter that allows the **AIS-Agent-Platform** backend to serve the DRSearch frontend without breaking existing functionality.

---

## 2. Scope

This contract covers:

| Area | Included |
|------|----------|
| Chat streaming endpoint (`/chat/stream_log`) | ✅ Full SSE protocol, event schemas, ordering |
| Index options endpoint (`GET /index-options`) | ✅ Request/response schema |
| Feedback endpoints (`POST /feedback`, `PATCH /feedback`) | ✅ Request/response schemas |
| Trace endpoint (`POST /get_trace`) | ✅ Stub — returns 501 |
| File proxy endpoint (`GET /files/{path}`) | ⚠️ Documented but not consumed by frontend JS code |
| Authentication middleware | ✅ Bearer token handling, whitelisting |
| CORS configuration | ✅ |

**Out of scope**: Internal chain orchestration details (LangChain internals, prompt templates, retriever configuration) — only their externally visible contract matters.

---

## 3. Source of Truth and Evidence Method

| Priority | Source | Role |
|----------|--------|------|
| 1 (Primary) | Frontend source code | Defines what the frontend **actually sends and parses** |
| 2 (Validation) | Backend route/model code | Confirms what the server **actually accepts and emits** |
| 3 (Supporting) | Test fixtures, SSE traces, E2E tests | Corroborates inferred behavior with concrete examples |

### Key Source Files

**Frontend** (in `drsearch_frontend/`):
- `app/utils/constants.tsx` — Backend base URL
- `app/utils/fetchIndexOptions.ts` — Index options client
- `app/utils/sendFeedback.tsx` — Feedback client
- `app/components/ChatWindow.tsx` — Streaming chat client (primary)
- `app/components/ChatMessageBubble.tsx` — Source/citation rendering
- `app/components/SourceBubble.tsx` — Source type definition
- `app/components/SourceList.tsx` — Source list rendering
- `app/components/InlineCitation.tsx` — Citation link rendering
- `app/components/BuildInfoWidget.tsx` — Build info consumer
- `app/utils/urlUtils.ts` — UNC path → URL conversion

**Backend** (in `drsearch_backend/`):
- `app/__init__.py` — App factory, middleware stack
- `app/api/v1/routes.py` — All route definitions
- `app/models/chat.py` — `ChatRequest` model
- `app/models/feedback.py` — `Feedback`, `FeedbackUpdate` models
- `app/models/shared.py` — `StandardResponse`, `IndexOption`, `IndexOptionsResponse`, `BuildInfo`
- `app/models/trace.py` — `TraceRequest` model
- `app/auth/middleware.py` — Auth middleware
- `app/chain/api.py` — LangServe chain binding (`answer_chain`)
- `app/chain/engine.py` — Chain construction (FindDocs naming)

**Test Evidence**:
- `drsearch_frontend/testing_full_app/traces/trace1.sse` — Real SSE recording
- `drsearch_frontend/testing_full_app/payload1.json` — Test request payload
- `drsearch_backend/tests/test_api_routes.py` — Backend route tests

---

## 4. Frontend-Consumed Endpoint Inventory

| # | Endpoint | Method | Transport | Frontend Consumer | Backend Handler |
|---|----------|--------|-----------|-------------------|-----------------|
| 1 | `/index-options` | GET | JSON | `fetchIndexOptions.ts`, `BuildInfoWidget.tsx` | `routes.py:index_options()` |
| 2 | `/chat/stream_log` | POST | SSE | `ChatWindow.tsx` | LangServe auto-route via `add_routes()` |
| 3 | `/feedback` | POST | JSON | `sendFeedback.tsx` | `routes.py:create_feedback()` |
| 4 | `/feedback` | PATCH | JSON | `sendFeedback.tsx` | `routes.py:patch_feedback()` |

### Endpoints NOT consumed by frontend (but defined on backend)
| Endpoint | Method | Notes |
|----------|--------|-------|
| `/get_trace` | POST | Returns 501. Not called by production frontend code. |
| `/files/{file_path:path}` | GET | File proxy. Frontend links to source URLs directly, not through this proxy. |
| `/chat/invoke` | POST | LangServe auto-route. Frontend uses `stream_log`, not `invoke`. |
| `/chat/stream` | POST | LangServe auto-route. Frontend uses `stream_log`, not `stream`. |
| `/chat/input_schema` | GET | LangServe auto-route. Not consumed by frontend. |
| `/chat/output_schema` | GET | LangServe auto-route. Not consumed by frontend. |
| `/chat/config_schema` | GET | LangServe auto-route. Not consumed by frontend. |
| `/chat/playground/*` | GET | LangServe playground. Not consumed by frontend. |

---

## 5. Request Contracts

### 5.1 `GET /index-options`

**Request**:
```
GET /index-options HTTP/1.1
Authorization: Bearer <token>   (optional — endpoint is auth-whitelisted)
```

- No request body
- No query parameters
- Authorization header is sent by frontend when `AUTH_ENABLED=true`, but the backend auth middleware **whitelists** this path so the token is not validated

**Evidence**: `fetchIndexOptions.ts:21-23`, `middleware.py:24-28`

---

### 5.2 `POST /chat/stream_log`

**Request**:
```
POST /chat/stream_log HTTP/1.1
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <token>   (required when AUTH_ENABLED=true)
```

**Request Body** (JSON):
```json
{
  "input": {
    "question": "How do I test a next.js frontend?",
    "chat_history": [
      { "human": "Hi", "ai": "Hello!" }
    ],
    "index_name": "JACSKE_Program",
    "num_docs_retrieved": 3
  },
  "config": {
    "metadata": {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "include_names": ["FindDocs"]
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `input.question` | `string` | **Yes** | — | User's natural language query |
| `input.chat_history` | `Array<{human: string, ai: string}>` | No | `[]` | Prior conversation turns |
| `input.index_name` | `string` | **Yes** (frontend enforces) | Backend default: `_DEFAULT_INDEX` | Selected document index name |
| `input.num_docs_retrieved` | `number` | No | `3` | Range: 1–5 |
| `config.metadata.conversation_id` | `string` (UUID) | No | — | Conversation tracking ID |
| `include_names` | `string[]` | **Yes** | — | Must include `"FindDocs"` to receive source documents |

**Note**: The `input` object is unwrapped by LangServe and passed to the chain as a `ChatRequest`. The `config` and `include_names` are LangServe protocol fields that control streaming behavior.

**Note**: The backend `ChatRequest` model also accepts `page_window` (int, default 0, range -1 to 50) but the frontend does **not** send this field.

**Evidence**: `ChatWindow.tsx:179-191`, `chat.py:13-37`, `payload1.json`

---

### 5.3 `POST /feedback`

**Request**:
```
POST /feedback HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>   (when AUTH_ENABLED=true)
```

**Request Body** (JSON):
```json
{
  "score": 1,
  "run_id": "c34dc77f-3e01-4df1-bc9f-ae2a6ae151bc",
  "key": "user_score",
  "value": "https://example.com/doc.pdf",
  "feedback_id": "550e8400-e29b-41d4-a716-446655440000",
  "comment": "Very helpful answer",
  "conversation": [
    { "role": "user", "content": "What is X?" },
    { "role": "assistant", "content": "X is..." }
  ],
  "documents": ["https://example.com/doc.pdf"],
  "source_info": {
    "is_explicit": true
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | `string` (UUID) | **Yes** | LangChain run ID from streaming response |
| `key` | `string` | **Yes** | One of: `"user_score"`, `"feedback_only"`, `"user_click"` |
| `score` | `number \| undefined` | No | `1` = thumbs up, `0` = thumbs down, omitted for comment-only |
| `value` | `string` | No | Used for click tracking (source URL) |
| `feedback_id` | `string` (UUID) | No for POST | Auto-generated by frontend if not provided |
| `comment` | `string` | No | User's text feedback |
| `conversation` | `Array<{role, content}>` | No | Full conversation for context |
| `documents` | `string[]` | No | List of source URLs |
| `source_info` | `{is_explicit: boolean}` | No | **⚠️ Drift**: Sent by frontend but NOT in backend Pydantic model — silently ignored by Pydantic v1 |

**Evidence**: `sendFeedback.tsx:24-62`, `feedback.py:11-20`

---

### 5.4 `PATCH /feedback`

Same endpoint and body as POST, but uses PATCH method when `feedbackId` is already known.

**Difference**: The `feedback_id` field MUST be present and non-null. Backend returns HTTP 400 if missing.

**Backend model**: `FeedbackUpdate` (simpler than `Feedback`):

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `feedback_id` | `string` (UUID) | **Yes** | Must be non-null |
| `score` | `number \| null` | No | |
| `comment` | `string` | No | |

**⚠️ Note**: The frontend sends the same full body for both POST and PATCH. The backend PATCH endpoint uses `FeedbackUpdate` which only accepts `feedback_id`, `score`, and `comment`. All other fields (run_id, key, value, conversation, documents, source_info) are silently ignored.

**Evidence**: `sendFeedback.tsx:38`, `feedback.py:23-29`, `test_api_routes.py:57-70`

---

## 6. Response Contracts

### 6.1 `GET /index-options` Response

**HTTP 200**:
```json
{
  "code": 200,
  "result": [
    {
      "name": "JACSKE_Program",
      "display_name": "JACSKE Program",
      "example_questions": [
        "What should the output power of the TR Module be?"
      ],
      "initialized": true,
      "acronyms": {
        "CDR": "Critical Design Review",
        "TR": "Transmit/Receive"
      }
    }
  ],
  "build_info": {
    "sha": "abcdef1234567890",
    "sha_short": "abcdef1",
    "build_date": "2024-05-01T12:00:00Z"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `code` | `number` | **Yes** | Must be `200` — frontend checks `data.code !== 200` |
| `result` | `IndexOption[]` | **Yes** | Must be an array — frontend checks `Array.isArray(data.result)` |
| `result[].name` | `string` | **Yes** | Used as index identifier in chat requests |
| `result[].display_name` | `string \| null` | No | Shown in dropdown UI |
| `result[].example_questions` | `string[] \| null` | No | Shown in empty state |
| `result[].initialized` | `boolean` | **Yes** | `false` disables the option in the dropdown |
| `result[].acronyms` | `Record<string, string> \| null` | No | Used for autocomplete in input editor |
| `build_info` | `BuildInfo \| null` | No | Omitted when env vars not set. Field excluded from JSON when null (`response_model_exclude_none=True`). |
| `build_info.sha` | `string` | Yes (if build_info present) | Full git SHA |
| `build_info.sha_short` | `string` | Yes (if build_info present) | Short git SHA |
| `build_info.build_date` | `string` | Yes (if build_info present) | ISO 8601 timestamp |

**Frontend validation** (`fetchIndexOptions.ts:31-32`):
```typescript
if (data.code !== 200 || !Array.isArray(data.result))
  throw new Error("Backend returned malformed data");
```

**Evidence**: `fetchIndexOptions.ts:30-33`, `shared.py:35-41`, `BuildInfoWidget.tsx:43-69`, `test_api_routes.py:13-54`

---

### 6.2 `POST /chat/stream_log` Response

SSE stream — see Sections 7 and 8 for full protocol details.

---

### 6.3 `POST /feedback` Response

**HTTP 200**:
```json
{
  "result": "posted feedback successfully",
  "code": 200
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `result` | `string` | **Yes** | |
| `code` | `number` | **Yes** | Frontend checks `data.code === 200` |

**Frontend post-processing** (`sendFeedback.tsx:58-61`): The frontend adds `feedbackId` to the response:
```typescript
return { ...data, feedbackId: feedback_id } as FeedbackResponse;
```

**⚠️ Note**: The backend does NOT return a `feedbackId` field. The frontend synthesizes it from the locally generated UUID.

**Evidence**: `sendFeedback.tsx:57-61`, `routes.py:103-113`

---

### 6.4 `PATCH /feedback` Response

**HTTP 200** (same as POST):
```json
{
  "result": "patched feedback successfully",
  "code": 200
}
```

**HTTP 400** (missing feedback_id):
```json
{
  "detail": "Missing feedback_id"
}
```

**Evidence**: `routes.py:115-121`, `test_api_routes.py:156-167`

---

## 7. Streaming Protocol Contract

### 7.1 Transport

| Property | Value |
|----------|-------|
| Protocol | Server-Sent Events (SSE) |
| Content-Type | `text/event-stream` |
| HTTP Method | POST |
| Client Library | `@microsoft/fetch-event-source` v2.0.1 |
| Patch Library | `fast-json-patch` v3.1.1 |

### 7.2 SSE Frame Format

Each SSE frame follows this exact format (note: `event:` comes before `data:`):

```
event: data
data: {"ops":[...]}

```

Termination frame:
```
event: end

```

**Key detail**: The `event` field name is `data` (not `message`). The frontend explicitly checks `msg.event === "data"` and `msg.event === "end"`.

### 7.3 Patch Accumulation Protocol

The streaming protocol is **LangServe's `stream_log` protocol**:

1. Each `event: data` frame contains a JSON object with an `ops` field
2. `ops` is an array of [RFC 6902 JSON Patch](https://datatracker.ietf.org/doc/html/rfc6902) operations
3. The frontend maintains a persistent `streamedResponse` object and applies patches incrementally:

```typescript
streamedResponse = applyPatch(streamedResponse, chunk.ops).newDocument;
```

4. The accumulated document has this shape after all patches are applied:

```typescript
{
  id: string;                    // Run ID (UUID)
  streamed_output: string[];     // Array of text token chunks
  final_output: string | null;   // Final complete output (set at end)
  logs: {
    [runName: string]: {
      id: string;
      name: string;
      type: string;              // "chain", "llm", "prompt", "parser"
      tags: string[];
      metadata: Record<string, any>;
      start_time: string;        // ISO 8601
      streamed_output: any[];
      streamed_output_str: string[];
      final_output: any | null;
      end_time: string | null;   // ISO 8601 or null while running
    };
    FindDocs?: {                 // Present when include_names includes "FindDocs"
      final_output: {
        output: Document[];      // Retrieved source documents
      };
    };
  };
  name: string;                  // Root chain name (e.g., "/chat")
  type: string;                  // "chain"
}
```

### 7.4 Frontend Extraction Logic

From `ChatWindow.tsx:218-234`:

```typescript
const doc = streamedResponse;

// 1. Extract sources (when available)
if (Array.isArray(doc.logs?.FindDocs?.final_output?.output)) {
  sources = doc.logs.FindDocs.final_output.output.map((d: any) => ({
    url: d.metadata.file_path,
    title: d.metadata.filename,
  }));
}

// 2. Track run ID
if (doc.id) runId = doc.id;

// 3. Accumulate streamed text
if (Array.isArray(doc.streamed_output)) {
  accumulated = doc.streamed_output.join("");
}
```

**Evidence**: `ChatWindow.tsx:199-257`, `trace1.sse` (full recording)

---

## 8. Streaming Event Definitions

### 8.1 `event: data`

**Payload**: JSON object with `ops` field.

```json
{
  "ops": [
    {
      "op": "replace" | "add" | "remove" | "move" | "copy" | "test",
      "path": "/some/json/pointer",
      "value": <any>
    }
  ]
}
```

The `ops` array contains standard JSON Patch operations (RFC 6902). In practice, LangServe emits primarily `replace` (for initial state) and `add` (for incremental updates).

### 8.2 Critical Patch Paths

These are the JSON Pointer paths the frontend actually reads:

| Path | Type | When Set | Frontend Usage |
|------|------|----------|----------------|
| `/id` | `string` | First `replace` event | Run ID for feedback |
| `/streamed_output/-` | `string` | Each LLM token | Appended to streamed text array; joined for display |
| `/logs/FindDocs` | `object` | When retriever starts | Creates the FindDocs log entry |
| `/logs/FindDocs/final_output` | `object` | When retriever completes | Contains source documents |
| `/logs/FindDocs/final_output/output` | `Document[]` | When retriever completes | Source document array |

### 8.3 `event: end`

**Payload**: None (empty data field or no data field).

The frontend handler:
```typescript
if (msg.event === "end") {
  setChatHistory((h) => [...h, { human: messageValue, ai: accumulated }]);
  setIsLoading(false);
  return;
}
```

This event signals:
1. Stream is complete
2. Chat history should be updated
3. Loading state should be cleared

### 8.4 Source Document Shape (in FindDocs output)

Each document in `FindDocs.final_output.output`:

```json
{
  "page_content": "This is the document text content.",
  "metadata": {
    "url": "https://example.com/doc.pdf",
    "filename": "ABC-123.pdf",
    "file_path": "\\\\server\\share\\docs\\ABC-123.pdf",
    "text_as_html": "<p>This is the document text content.</p>"
  },
  "type": "Document"
}
```

**Frontend extracts only**:
- `d.metadata.file_path` → mapped to `source.url`
- `d.metadata.filename` → mapped to `source.title`

All other metadata fields (`url`, `text_as_html`, `page_content`, etc.) are **ignored by the frontend** source rendering logic.

**Evidence**: `ChatWindow.tsx:222-225`, `trace1.sse` (FindDocs final_output event)

---

## 9. Ordering Rules and Frontend State Assumptions

### 9.1 Event Ordering

Based on LangServe's `stream_log` protocol and confirmed by trace recordings:

```
1. event: data  →  ops: [replace / at root]     (initial state with id, empty streamed_output)
2. event: data  →  ops: [add /logs/*]            (chain execution logs, order varies)
3. event: data  →  ops: [add /logs/FindDocs]     (retriever starts — may be early or late)
4. event: data  →  ops: [add /streamed_output/-] (first LLM token)
   ...
   (interleaved: more tokens + FindDocs completion)
   ...
N. event: data  →  ops: [add /logs/FindDocs/final_output] (sources available)
   ...
   (more LLM tokens may follow)
   ...
M. event: end                                     (stream complete)
```

### 9.2 Key Ordering Invariants

1. **The root `id` is set in the first event** — via `"op": "replace", "path": ""` with initial state
2. **Sources can arrive BEFORE the final LLM token** — FindDocs retrieval completes independently from LLM generation
3. **Sources can arrive AFTER some LLM tokens** — the frontend handles this gracefully by updating sources on every event
4. **`streamed_output` is an array** — tokens are appended via `"op": "add", "path": "/streamed_output/-"`
5. **The `end` event is always last** — no data events follow it
6. **Multiple ops can be in a single event** — the `ops` array can contain multiple patch operations

### 9.3 Frontend State Machine

```
IDLE → [user sends message] → LOADING
LOADING → [first data event] → STREAMING
STREAMING → [each data event] → STREAMING (update text, sources, runId)
STREAMING → [end event] → IDLE (update chat history, clear loading)
STREAMING → [error] → IDLE (revert last message, restore input)
```

---

## 10. Error Handling Contract

### 10.1 HTTP-Level Errors

| Status | Condition | Frontend Handling |
|--------|-----------|-------------------|
| 401 | Missing/invalid Bearer token | `fetchEventSource` `onerror` callback throws, catch block reverts message |
| 422 | Pydantic validation failure | Same as above |
| 500 | Server error | Same as above |

### 10.2 Streaming Errors

The `fetchEventSource` library handles SSE connection errors via the `onerror` callback:

```typescript
onerror(err) {
  console.error("Error in EventSource:", err);
  throw err;  // Propagates to catch block
}
```

The catch block (`ChatWindow.tsx:260-271`):
1. Logs the error to console
2. Removes the last message (the partial assistant response)
3. Clears loading state
4. Restores the user's input text

### 10.3 Non-Streaming Error Handling

**`/index-options`** (`fetchIndexOptions.ts:24-32`):
- HTTP non-OK: throws `Error("Failed to fetch index options: {status} – {text}")` → displayed via `toast.error()`
- Malformed response (`code !== 200` or non-array `result`): throws `Error("Backend returned malformed data")`

**`/feedback`** (`sendFeedback.tsx:57`):
- Response is parsed as JSON unconditionally
- Frontend checks `data.code === 200` to determine success (`ChatMessageBubble.tsx:287`)
- No explicit HTTP error handling — errors propagate to caller's catch block

### 10.4 Backend Error Response Formats

Standard FastAPI error:
```json
{
  "detail": "Error message string"
}
```

Application-level error (from `StandardResponse`):
```json
{
  "result": "error message",
  "code": 500
}
```

---

## 11. Source / Citation Contract

### 11.1 Source Data Flow

```
Backend (FindDocs) → SSE Stream → Frontend State → Dedup → Citation Filter → Render
```

### 11.2 Source Type

Defined in `SourceBubble.tsx:9-12`:
```typescript
export type Source = {
  url: string | undefined;
  title: string;
};
```

### 11.3 Source Extraction from Stream

From `ChatWindow.tsx:221-226`:
```typescript
if (Array.isArray(doc.logs?.FindDocs?.final_output?.output)) {
  sources = doc.logs.FindDocs.final_output.output.map((d: any) => ({
    url: d.metadata.file_path,    // UNC path or URL
    title: d.metadata.filename,    // Document filename / part number
  }));
}
```

**Critical**: The frontend uses `file_path` (not `url`) from metadata for the source URL. The `file_path` field is enriched by the backend's `PartNumberMapping` from a PostgreSQL table that maps filenames to UNC file paths.

### 11.4 Source Deduplication

`ChatMessageBubble.tsx:64-95` — `filterSources()`:
1. Iterates sources in order
2. Deduplicates by `url` field
3. Builds an `indexMap` mapping original indices to deduplicated indices
4. Sources with `undefined` url are skipped (with console warning)

### 11.5 Citation Filtering

`ChatMessageBubble.tsx:97-135` — `filterSourcesByCitations()`:
1. Parses citation references from the rendered content using regex
2. Keeps only sources that are actually cited in the text
3. Remaps citation numbers to new sequential indices

### 11.6 Citation Regex

```typescript
const citationRegex = /\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g;
```

Matches:
- `[1]` — standard
- `[$1]` — dollar prefix
- `[^1^]` — caret wrapped
- `[ 1 ]` — with spaces

The captured group is the **0-based index** into the source array.

### 11.7 URL Conversion

`urlUtils.ts` — `convertToHttpUrlIfNeeded()`:
- UNC paths matching `//home.drs.com@ssl/DavWWWRoot/...` → `https://home.drs.com/{path}?web=1`
- SEPS paths matching `SEPS_DOCS/docs/...` → `https://company.sharepoint.us/sites/SEPs/{path}.docx?web=1`
- All other paths returned unchanged

### 11.8 Citation Rendering

`InlineCitation.tsx`: Renders as `<a>` tags with:
- `href`: converted URL
- `target="_blank"`
- Display: source number (1-based)

### 11.9 LLM Citation Format Requirement

The LLM must emit citations in the response text using bracket notation that matches the regex above. The number inside brackets is **0-based** and corresponds to the index in the `FindDocs.final_output.output` array.

Example LLM output:
```
The TR Module output power should be 10W [0]. See also the receiver specifications [1].
```

---

## 12. Session, Conversation, and Context Handling

### 12.1 Conversation ID

- Generated client-side as UUID v4 (`ChatWindow.tsx:46`)
- Sent in request as `config.metadata.conversation_id`
- Reset when: index changes, "new chat" button clicked
- **Not stored server-side** — the backend does not maintain session state

### 12.2 Chat History

- Maintained client-side in `chatHistory` state (`ChatWindow.tsx:54-56`)
- Shape: `Array<{ human: string, ai: string }>`
- Updated on `event: end` with the completed message pair
- Sent in every subsequent request as `input.chat_history`
- Reset when: index changes, "new chat" button clicked
- **The backend does not persist chat history** — it relies entirely on the frontend sending the full history

### 12.3 Messages State

- `messages` array contains all displayed messages (`ChatWindow.tsx:51`)
- Each message: `{ id: string, content: string, role: string, runId?: string, sources?: Source[] }`
- Content is **parsed Markdown** (HTML string) via `marked`
- Messages are rendered in reverse order (newest first)

### 12.4 State Reset Behavior

On index change (`ChatWindow.tsx:83-91`):
```typescript
setMessages([]);
setChatHistory([]);
setInput("");
setConversationId(uuidv4());
```

On "new chat" (`ChatWindow.tsx:278-286`): Same reset behavior.

---

## 13. Headers, Auth, and Environment Assumptions

### 13.1 Environment Variables (Frontend)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8011` | Backend base URL |
| `NEXT_PUBLIC_AUTH_ENABLED` | — | `"False"` disables auth; any other value enables it |
| `NEXT_PUBLIC_DEV_ACCESS_TOKEN` | `""` | Used as bearer token in dev mode when auth disabled |
| `NEXT_PUBLIC_AZURE_AD_CLIENT_ID` | — | Azure AD app registration client ID |
| `NEXT_PUBLIC_AZURE_AD_TENANT_ID` | — | Azure AD tenant ID |

### 13.2 Request Headers

**Streaming chat** (`ChatWindow.tsx:172-176`):
```
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <token>    (when AUTH_ENABLED)
```

**Index options** (`fetchIndexOptions.ts:20-21`):
```
Authorization: Bearer <token>    (when token provided)
```

**Feedback** (`sendFeedback.tsx:39-41`):
```
Content-Type: application/json
Authorization: Bearer <token>    (when accessToken provided)
```

### 13.3 Backend Auth Middleware

- Auth middleware (`auth/middleware.py`) validates Azure AD JWT tokens
- Whitelisted paths (no auth required): `/chat/playground`, `/favicon.ico`, `/index-options`
- Auth can be disabled entirely via `AUTH_ENABLED=False` env var
- When disabled, sets `request.state.user = {"username": "devuser"}`
- CORS options (preflight) requests are always allowed through

### 13.4 CORS Configuration

From `app/__init__.py:29-35`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # From CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 14. Required vs Optional Fields

### 14.1 Request Fields — Criticality Matrix

#### `/chat/stream_log` Request

| Field | Required by Frontend | Required by Backend | Notes |
|-------|---------------------|---------------------|-------|
| `input.question` | ✅ | ✅ | Pydantic `Field(...)` — no default |
| `input.chat_history` | ✅ (always sent) | No (default: `None`) | Frontend always sends it, even as `[]` |
| `input.index_name` | ✅ (enforced by UI) | No (default: `_DEFAULT_INDEX`) | Frontend blocks send without selection |
| `input.num_docs_retrieved` | ✅ (always sent) | No (default: `3`) | Frontend defaults to `3` via state |
| `input.page_window` | ❌ (never sent) | No (default: `0`) | Backend accepts but frontend doesn't send |
| `config` | ✅ (always sent) | No | LangServe metadata |
| `config.metadata.conversation_id` | ✅ (always sent) | No | Passed through to chain metadata |
| `include_names` | ✅ (always sent) | No | Must be `["FindDocs"]` to receive sources |

#### `/index-options` Response

| Field | Required by Frontend | Notes |
|-------|---------------------|-------|
| `code` | ✅ | Must be `200` |
| `result` | ✅ | Must be an array |
| `result[].name` | ✅ | Used as option value |
| `result[].display_name` | No | Falls through to display |
| `result[].initialized` | ✅ | Controls disabled state |
| `result[].example_questions` | No | Used in empty state |
| `result[].acronyms` | No | Used for autocomplete |
| `build_info` | No | Consumed by BuildInfoWidget |

#### `/feedback` Request

| Field | Required by Frontend | Required by Backend | Notes |
|-------|---------------------|---------------------|-------|
| `run_id` | ✅ | ✅ | UUID format |
| `key` | ✅ | No (default: `"user_score"`) | |
| `score` | No | No | |
| `feedback_id` | ✅ (always generated) | No for POST, **Yes** for PATCH | |
| `comment` | No | No | |
| `conversation` | No | No | |
| `documents` | No | No | |
| `value` | No | ❌ Not in model | Silently ignored by Pydantic v1 |
| `source_info` | No | ❌ Not in model | Silently ignored by Pydantic v1 |

---

## 15. Compatibility Invariants

These are the hard requirements a compatible backend **must** preserve:

### 15.1 Must-Have Invariants

1. **`GET /index-options` must return `{ code: 200, result: [...] }`** — Frontend throws if `code !== 200` or `result` is not an array.

2. **`POST /chat/stream_log` must use SSE with LangServe's `stream_log` protocol** — The frontend uses JSON Patch accumulation. A simple SSE text stream will NOT work.

3. **SSE events must use `event: data` and `event: end` names** — Not `event: message` or unnamed events.

4. **Each `event: data` must contain JSON with an `ops` array of RFC 6902 JSON Patch operations** — The frontend calls `applyPatch(streamedResponse, chunk.ops)`.

5. **The accumulated document must have an `id` field** — Used as run ID for feedback.

6. **The accumulated document must have a `streamed_output` array of strings** — Joined to form the response text.

7. **Sources must be at `logs.FindDocs.final_output.output`** — The frontend checks this exact path.

8. **Each source document must have `metadata.file_path` and `metadata.filename`** — Mapped to `url` and `title`.

9. **The stream must terminate with `event: end`** — Without this, the frontend stays in loading state forever.

10. **`POST /feedback` must return `{ code: 200, result: "..." }`** — Frontend checks `data.code === 200`.

### 15.2 Should-Have Invariants

1. **LLM responses should include bracket citations** matching `/\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g` — If not present, no citations are rendered (graceful degradation).

2. **Citation numbers should be 0-based indices** into the FindDocs output array.

3. **`/index-options` should include `build_info`** when available — BuildInfoWidget displays it but handles null gracefully.

4. **Auth middleware should whitelist `/index-options`** — Frontend may call it without a token.

---

## 16. Known Ambiguities and Open Questions

### 16.1 Confirmed Ambiguities

| # | Issue | Evidence | Impact |
|---|-------|----------|--------|
| 1 | Frontend sends `value` and `source_info` in feedback but backend model doesn't define them | `sendFeedback.tsx:47,52-54` vs `feedback.py:11-20` | Low — Pydantic v1 silently ignores extra fields. Pydantic v2 would reject them unless `model_config = ConfigDict(extra='ignore')` |
| 2 | Backend port mismatch: frontend defaults to `8011`, backend runs on `8010` | `constants.tsx:3-4` vs `main.py` | Resolved by `NEXT_PUBLIC_API_BASE_URL` env var or Docker networking. Not a contract issue. |
| 3 | JS backend route exists but is not used | `app/api/chat/stream_log/route.ts:3` | Confirmed dead code. Comment says "JS backend not used by default". |

### 16.2 Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | What happens if `include_names` is omitted or empty? | **Unverified** | LangServe likely returns all log entries. Frontend relies on `FindDocs` being present. |
| 2 | Does the backend emit any error events via SSE? | **Unverified** | LangServe may emit error events on chain failure. Frontend's `onerror` handler would catch connection-level errors, but mid-stream chain errors are undocumented. |
| 3 | Is there a maximum SSE connection timeout? | **Unverified** | Depends on infrastructure (reverse proxies, load balancers). No explicit timeout in frontend code. |
| 4 | Are there rate limits on any endpoint? | **Unverified** | No rate limiting middleware visible in backend code. |
| 5 | Does `PATCH /feedback` actually update existing feedback? | **Uncertain** | Backend only logs the patch body; no persistence layer for feedback updates is visible. |

---

## 17. Recommended AIS-Agent-Platform Adapter Boundary

### 17.1 Adapter Strategy

The recommended approach is a **compatibility adapter** that sits between the DRSearch frontend and the AIS-Agent-Platform backend, translating the LangServe `stream_log` protocol to/from whatever protocol AIS-Agent-Platform uses.

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│  DRSearch    │────▶│  Compatibility   │────▶│  AIS-Agent-Platform  │
│  Frontend    │◀────│  Adapter         │◀────│  Backend             │
└─────────────┘     └──────────────────┘     └──────────────────────┘
```

### 17.2 Adapter Responsibilities

1. **`GET /index-options`**: Translate AIS-Agent-Platform's index/collection listing to DRSearch's `IndexOptionsResponse` format.

2. **`POST /chat/stream_log`**: This is the critical endpoint.
   - Accept the LangServe-format request body
   - Extract `question`, `chat_history`, `index_name`, `num_docs_retrieved` from `input`
   - Forward to AIS-Agent-Platform's chat/completion API
   - Convert AIS-Agent-Platform's streaming response into LangServe `stream_log` SSE format
   - Emit proper JSON Patch operations to build up the expected document structure
   - Emit `FindDocs.final_output.output` with properly structured source documents
   - Emit `streamed_output/-` additions for each text token
   - Set `id` field on the accumulated document
   - Terminate with `event: end`

3. **`POST /feedback`** and **`PATCH /feedback`**: Accept and log/forward feedback. Return `{ code: 200, result: "..." }`.

### 17.3 Minimum Viable Adapter

For a minimal adapter that makes the frontend work:

1. Implement `GET /index-options` returning hardcoded or fetched options
2. Implement `POST /chat/stream_log` with:
   - First event: `replace` at root with `{ id: "<uuid>", streamed_output: [], logs: {}, ... }`
   - Source events: `add` at `/logs/FindDocs` and `/logs/FindDocs/final_output`
   - Token events: `add` at `/streamed_output/-` for each text chunk
   - Final event: `event: end`
3. Implement `POST /feedback` returning `{ code: 200, result: "ok" }`

### 17.4 SSE Generation Example (Pseudocode)

```python
# First event — initialize document
yield f"event: data\ndata: {json.dumps({'ops': [{'op': 'replace', 'path': '', 'value': {'id': run_id, 'streamed_output': [], 'final_output': None, 'logs': {}, 'name': '/chat', 'type': 'chain'}}]})}\n\n"

# Source documents available
yield f"event: data\ndata: {json.dumps({'ops': [{'op': 'add', 'path': '/logs/FindDocs', 'value': {'id': find_docs_id, 'name': 'FindDocs', 'type': 'chain', 'tags': [], 'metadata': {}, 'start_time': now, 'streamed_output': [], 'streamed_output_str': [], 'final_output': None, 'end_time': None}}]})}\n\n"

yield f"event: data\ndata: {json.dumps({'ops': [{'op': 'add', 'path': '/logs/FindDocs/final_output', 'value': {'output': sources_as_documents}}, {'op': 'add', 'path': '/logs/FindDocs/end_time', 'value': now}]})}\n\n"

# Stream each token
for token in llm_tokens:
    yield f"event: data\ndata: {json.dumps({'ops': [{'op': 'add', 'path': '/streamed_output/-', 'value': token}]})}\n\n"

# Terminate
yield "event: end\n\n"
```

---

## 18. Concrete Examples

### 18.1 Complete Chat Request Example

```http
POST /chat/stream_log HTTP/1.1
Host: localhost:8011
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...

{
  "input": {
    "question": "How do I test a next.js frontend?",
    "chat_history": [
      { "human": "Hi", "ai": "Hello!" }
    ],
    "index_name": "JACSKE_Program",
    "num_docs_retrieved": 3
  },
  "config": {
    "metadata": {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "include_names": ["FindDocs"]
}
```

### 18.2 SSE Stream Example (Simplified)

```
event: data
data: {"ops":[{"op":"replace","path":"","value":{"id":"c34dc77f-3e01-4df1-bc9f-ae2a6ae151bc","streamed_output":[],"final_output":null,"logs":{},"name":"/chat","type":"chain"}}]}

event: data
data: {"ops":[{"op":"add","path":"/logs/FindDocs","value":{"id":"c89e1851-6305-4dde-b66f-a0f45d8ac35a","name":"FindDocs","type":"chain","tags":["seq:step:1"],"metadata":{},"start_time":"2025-06-24T15:09:24.663+00:00","streamed_output":[],"streamed_output_str":[],"final_output":null,"end_time":null}}]}

event: data
data: {"ops":[{"op":"add","path":"/logs/FindDocs/final_output","value":{"output":[{"page_content":"Test content about next.js testing.","metadata":{"url":"https://example.com/doc1.pdf","filename":"doc1.txt","file_path":"/docs/doc1.txt","text_as_html":"<p>Test content.</p>"},"type":"Document"}]}},{"op":"add","path":"/logs/FindDocs/end_time","value":"2025-06-24T15:09:28.333+00:00"}]}

event: data
data: {"ops":[{"op":"add","path":"/streamed_output/-","value":"To test"}]}

event: data
data: {"ops":[{"op":"add","path":"/streamed_output/-","value":" a Next"}]}

event: data
data: {"ops":[{"op":"add","path":"/streamed_output/-","value":".js frontend"}]}

event: data
data: {"ops":[{"op":"add","path":"/streamed_output/-","value":", use Jest [0]."}]}

event: end

```

### 18.3 Index Options Response Example

```json
{
  "code": 200,
  "result": [
    {
      "name": "JACSKE_Program",
      "display_name": "JACSKE Program",
      "example_questions": [
        "What should the output power of the TR Module be?",
        "Where in the Receiver-Transmitter is the XMIT Trigger generated?"
      ],
      "initialized": true,
      "acronyms": {
        "CDR": "Critical Design Review",
        "TR": "Transmit/Receive"
      }
    },
    {
      "name": "SEPS_AFTER_MIGRATION",
      "display_name": "SEPS After Migration",
      "initialized": false
    }
  ],
  "build_info": {
    "sha": "abcdef1234567890abcdef1234567890abcdef12",
    "sha_short": "abcdef1",
    "build_date": "2024-05-01T12:00:00Z"
  }
}
```

### 18.4 Feedback POST Request Example

```http
POST /feedback HTTP/1.1
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...

{
  "score": 1,
  "run_id": "c34dc77f-3e01-4df1-bc9f-ae2a6ae151bc",
  "key": "user_score",
  "feedback_id": "550e8400-e29b-41d4-a716-446655440000",
  "comment": "Very helpful answer",
  "conversation": [
    { "role": "user", "content": "How do I test a next.js frontend?" },
    { "role": "assistant", "content": "To test a Next.js frontend, use Jest [0]." }
  ],
  "documents": ["/docs/doc1.txt"],
  "source_info": { "is_explicit": true }
}
```

### 18.5 Feedback POST Response Example

```json
{
  "result": "posted feedback successfully",
  "code": 200
}
```

### 18.6 Source Click Feedback Example

```http
POST /feedback HTTP/1.1
Content-Type: application/json

{
  "run_id": "c34dc77f-3e01-4df1-bc9f-ae2a6ae151bc",
  "key": "user_click",
  "value": "https://home.drs.com/docs/doc1.txt?web=1",
  "feedback_id": "new-uuid-here",
  "source_info": { "is_explicit": false }
}
```

---

## 19. Evidence Summary / File References

| Evidence Item | File | Lines | What It Proves |
|---------------|------|-------|----------------|
| Backend base URL default | `drsearch_frontend/app/utils/constants.tsx` | 3-4 | Default: `http://localhost:8011` |
| Index options request | `drsearch_frontend/app/utils/fetchIndexOptions.ts` | 17-34 | GET `/index-options`, response validation |
| Feedback client | `drsearch_frontend/app/utils/sendFeedback.tsx` | 24-62 | POST/PATCH `/feedback`, request body shape |
| Chat streaming request | `drsearch_frontend/app/components/ChatWindow.tsx` | 172-191 | Headers, body, endpoint |
| SSE event parsing | `drsearch_frontend/app/components/ChatWindow.tsx` | 199-257 | Event names, patch accumulation, source extraction |
| Source type definition | `drsearch_frontend/app/components/SourceBubble.tsx` | 9-12 | `{ url, title }` |
| Citation regex | `drsearch_frontend/app/components/ChatMessageBubble.tsx` | 102, 151 | `/\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g` |
| Build info consumer | `drsearch_frontend/app/components/BuildInfoWidget.tsx` | 43-69 | Reads `build_info` from `/index-options` |
| URL conversion | `drsearch_frontend/app/utils/urlUtils.ts` | 1-31 | UNC path → HTTPS URL |
| Backend routes | `drsearch_backend/app/api/v1/routes.py` | 69-163 | All route definitions |
| LangServe binding | `drsearch_backend/app/api/v1/routes.py` | 73-79 | `add_routes(router, answer_chain, path="/chat")` |
| ChatRequest model | `drsearch_backend/app/models/chat.py` | 13-37 | Request schema with defaults |
| Feedback model | `drsearch_backend/app/models/feedback.py` | 11-20 | POST feedback schema |
| FeedbackUpdate model | `drsearch_backend/app/models/feedback.py` | 23-29 | PATCH feedback schema |
| IndexOptionsResponse | `drsearch_backend/app/models/shared.py` | 35-41 | Response schema |
| Auth middleware | `drsearch_backend/app/auth/middleware.py` | 20-97 | Whitelist, token validation |
| FindDocs chain naming | `drsearch_backend/app/chain/engine.py` | 226 | `.with_config(run_name="FindDocs")` |
| SSE trace recording | `drsearch_frontend/testing_full_app/traces/trace1.sse` | All | Complete SSE stream example |
| Test payload | `drsearch_frontend/testing_full_app/payload1.json` | All | Request body format |
| Backend route tests | `drsearch_backend/tests/test_api_routes.py` | All | Validates response shapes |
| App factory + CORS | `drsearch_backend/app/__init__.py` | 16-52 | Middleware stack, CORS config |
