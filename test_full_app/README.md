# DRSearch End-to-End Test Suite

This directory contains the consolidated end-to-end (E2E) test suite for DRSearch. All E2E-related files have been moved here from their previous locations in `drsearch_backend/testing_full_app/` and `drsearch_frontend/testing_full_app/`.

## Directory Structure

```
test_full_app/
├── backend/                 # Backend simulator files
│   ├── __init__.py
│   ├── simulator.py         # FastAPI simulator
│   └── create_test_traces.ps1
├── frontend/                # Frontend test files
│   ├── e2e.spec.ts          # Happy path tests
│   ├── e2e_negative.spec.ts # Error scenario tests
│   ├── trace_utils.ts       # Trace parsing utilities
│   ├── payload1.json        # Test payloads
│   ├── payload2.json
│   ├── payload3.json
│   └── debug_trace.js
├── traces/                  # Consolidated trace files
│   ├── trace1.sse
│   ├── trace2.sse
│   └── trace3.sse
├── run-e2e.mjs             # Main test runner
├── run_e2e.sh              # Legacy shell runner
├── run_e2e.ps1             # Legacy PowerShell runner
└── logs/                   # Test execution logs
```

## Running the Tests

The tests can be executed using:

```bash
COLLECT_COVERAGE=1 node test_full_app/run-e2e.mjs
```

## Key Changes from Previous Structure

1. **Consolidated Location**: All E2E files are now in one place at the project root
2. **Unified Traces**: Only one copy of trace files exists in `test_full_app/traces/`
3. **Clear Separation**: Backend and frontend components are organized in separate subdirectories
4. **Updated Paths**: All import and reference paths have been updated to reflect the new structure

## Backend Simulator

The simulator (`backend/simulator.py`) provides a FastAPI application that replays pre-recorded SSE traces. It serves:
- `GET /index-options` - Returns available index definitions
- `POST /chat/stream_log` - Streams trace data as Server-Sent Events
- `GET /last_request` - Returns the most recent request for debugging

## Frontend Tests

The Playwright tests (`frontend/`) validate:
- Happy path scenarios with different payloads
- Error handling for backend failures
- Slow streaming behavior
- Malformed SSE handling

## Trace Files

The `.sse` files in `traces/` contain pre-recorded Server-Sent Events that simulate real backend responses for testing. 