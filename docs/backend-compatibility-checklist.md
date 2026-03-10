# Backend Compatibility Investigation Checklist

## Purpose
This checklist tracks progress for reverse-engineering the DRSearch backend contract required by the DRSearch frontend.

## Instructions
- Read this checklist first on every run.
- Update checkbox state as work progresses.
- Add dated notes under the relevant sections.
- Do not delete prior notes unless they are superseded and clearly replaced.
- Use this checklist as the continuity mechanism across repeated runs of the same prompt.

---

## 1. Setup and Discovery
- [x] Locate frontend backend-integration files
- [x] Locate backend route definitions relevant to frontend chat flows
- [x] Locate tests, fixtures, mocks, and related docs
- [x] Identify all candidate endpoints used by the frontend
- [x] Identify all environment/config settings that affect backend selection or request construction

### Notes
- 2026-03-10: Frontend files identified: `ChatWindow.tsx`, `ChatMessageBubble.tsx`, `SourceBubble.tsx`, `SourceList.tsx`, `InlineCitation.tsx`, `BuildInfoWidget.tsx`, `fetchIndexOptions.ts`, `sendFeedback.tsx`, `constants.tsx`, `urlUtils.ts`
- 2026-03-10: Backend routes in `app/api/v1/routes.py`: `/chat` (LangServe), `/index-options`, `/feedback` (POST/PATCH), `/get_trace`, `/files/{path}`
- 2026-03-10: Frontend consumes 4 primary endpoints: `GET /index-options`, `POST /chat/stream_log`, `POST /feedback`, `PATCH /feedback`
- 2026-03-10: Backend URL configured via `NEXT_PUBLIC_API_BASE_URL` env var, defaults to `http://localhost:8011`
- 2026-03-10: Auth controlled via `NEXT_PUBLIC_AUTH_ENABLED` env var
- 2026-03-10: SSE trace files found in `drsearch_frontend/testing_full_app/traces/` and `drsearch_backend/testing_full_app/traces/`
- 2026-03-10: LangServe `add_routes` auto-generates `/chat/stream_log` endpoint from the `answer_chain` Runnable

---

## 2. Frontend Contract Extraction
- [x] Identify all fetch/API client utilities
- [x] Identify all chat-related hooks/components/state managers
- [x] Extract all endpoint paths and HTTP methods
- [x] Extract request headers and auth assumptions
- [x] Extract request body schemas
- [x] Extract query params/path params if any
- [x] Extract response parsing logic for non-streaming endpoints
- [x] Extract streaming transport/protocol details
- [x] Extract streaming event names
- [x] Extract streaming payload shapes
- [x] Extract event ordering/state assumptions
- [x] Extract source/citation rendering dependencies
- [x] Extract error parsing and fallback behavior
- [x] Distinguish required fields from ignored/optional fields

### Notes
- 2026-03-10: Streaming uses `@microsoft/fetch-event-source` library with `fast-json-patch` for incremental state updates
- 2026-03-10: Two SSE event types consumed: `event: data` (JSON patch ops) and `event: end` (stream termination)
- 2026-03-10: Frontend extracts sources from `doc.logs.FindDocs.final_output.output` array
- 2026-03-10: Frontend extracts run ID from `doc.id`
- 2026-03-10: Frontend extracts streamed text from `doc.streamed_output` (array of string chunks joined)
- 2026-03-10: Citation regex: `/\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g`
- 2026-03-10: Source type expected: `{ url: string | undefined, title: string }`
- 2026-03-10: Sources mapped from documents: `url = d.metadata.file_path`, `title = d.metadata.filename`

---

## 3. Backend Validation
- [x] Match frontend-used endpoints to backend route implementations
- [x] Validate request schemas against backend models/parsers
- [x] Validate non-streaming response schemas
- [x] Validate streaming event generation
- [x] Validate event names and payload contents
- [x] Validate error event/response behavior
- [x] Validate source/citation payload structure
- [x] Identify route aliases, deprecated behavior, or multiple code paths
- [x] Identify contract mismatches or ambiguities between frontend and backend

### Notes
- 2026-03-10: LangServe auto-generates `/chat/stream_log` from `add_routes(router, answer_chain, path="/chat")`
- 2026-03-10: The JS backend route at `app/api/chat/stream_log/route.ts` is NOT used by default (comment says "JS backend not used by default")
- 2026-03-10: The Python backend uses LangServe which handles the SSE stream_log protocol automatically
- 2026-03-10: Frontend sends `source_info` field in feedback but backend `Feedback` model does NOT define it — Pydantic v1 silently ignores extra fields
- 2026-03-10: Frontend sends `value` field in feedback but backend `Feedback` model does NOT define it — also silently ignored
- 2026-03-10: Backend `Feedback.score` expects `Union[float, int, bool, None]` but frontend sends `number | undefined`
- 2026-03-10: Auth middleware whitelists `/index-options` and `/chat/playground` — no token needed for these

---

## 4. Tests and Runtime Evidence
- [x] Review backend tests
- [x] Review frontend tests
- [x] Review integration tests
- [x] Review mocks/fixtures/example payloads
- [x] Capture evidence that confirms or contradicts inferred contract behavior

### Notes
- 2026-03-10: Backend tests confirm `/index-options` response shape with `result` array and optional `build_info`
- 2026-03-10: Backend tests confirm `/feedback` POST returns 200 with StandardResponse, PATCH without feedback_id returns 400
- 2026-03-10: Frontend test payloads confirm request body shape: `{input: {question, chat_history, index_name, num_docs_retrieved}, config: {metadata: {conversation_id}}, include_names: ["FindDocs"]}`
- 2026-03-10: SSE trace files (trace1.sse) confirm the exact streaming protocol: JSON Patch operations via `event: data`, termination via `event: end`
- 2026-03-10: SSE trace confirms FindDocs.final_output.output contains array of Document objects with `page_content`, `metadata`, `type` fields
- 2026-03-10: E2E tests validate payload format and stream consumption

---

## 5. Contract Document Drafting
- [x] Create `docs/backend-compatibility-contract.md`
- [x] Write overview and scope
- [x] Write evidence methodology / source-of-truth section
- [x] Write endpoint inventory
- [x] Write request schema sections
- [x] Write response schema sections
- [x] Write streaming protocol section
- [x] Write event schema section
- [x] Write ordering/invariants section
- [x] Write error semantics section
- [x] Write source/citation schema section
- [x] Write session/context handling section
- [x] Write environment/auth assumptions section
- [x] Write required vs optional field analysis
- [x] Write compatibility risks section
- [x] Write recommended AIS-Agent-Platform adapter boundary
- [x] Write open questions / unverified items section
- [x] Add concrete request/response/event examples

### Notes
- 2026-03-10: Full contract document drafted with all 19 sections

---

## 6. Consistency and Completeness Review
- [x] Verify every frontend-used endpoint is documented
- [x] Verify every contract claim is backed by code evidence
- [x] Verify inferred behavior is clearly labeled
- [x] Verify ambiguous behavior is explicitly called out
- [x] Verify examples align with implementation
- [x] Verify no critical schema/protocol gaps remain
- [x] Verify checklist notes are current
- [x] Determine whether task is complete

### Notes
- 2026-03-10: All 4 frontend-consumed endpoints documented (GET /index-options, POST /chat/stream_log, POST /feedback, PATCH /feedback)
- 2026-03-10: All claims backed by specific file:line references
- 2026-03-10: Drift between frontend and backend documented (extra fields in feedback)
- 2026-03-10: Open questions documented in Section 16

---

## 7. Completion Criteria
Mark complete only when all of the following are true:

- [x] The contract document is complete enough for another engineer to implement a compatibility layer
- [x] Streaming behavior is documented precisely
- [x] Error behavior is documented precisely
- [x] Source/citation structures are documented precisely
- [x] Required vs optional fields are documented precisely
- [x] Open items are minimal and clearly identified
- [x] The checklist reflects the final state accurately

### Final Notes
- 2026-03-10: Contract document is complete. All major endpoints, schemas, streaming protocol, error handling, and source/citation structures are documented with code evidence.
