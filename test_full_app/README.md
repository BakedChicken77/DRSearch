# DRSearch End-to-End Test Suite

This directory contains the consolidated end-to-end (E2E) test suite for DRSearch. All E2E-related files have been moved here from their previous locations in `drsearch_backend/testing_full_app/` and `drsearch_frontend/testing_full_app/`.

## Directory Structure

```
test_full_app/
├── backend/                           # Backend E2E testing
│   ├── __init__.py                    # Python package init
│   ├── fake_components.py             # Deterministic fake LLM, embeddings, retriever
│   ├── test_backend_e2e_simple.py     # Simplified component tests (always work)
│   ├── test_backend_e2e_example.py    # Full backend API tests (see status below)
│   ├── test_config.py                 # Test environment configuration
│   ├── simulator.py                   # FastAPI simulator for frontend tests
│   └── create_test_traces.ps1         # Script to create test traces
├── frontend/                          # Frontend E2E testing
│   ├── e2e.spec.ts                    # Happy path tests
│   ├── e2e_negative.spec.ts           # Error scenario tests
│   ├── trace_utils.ts                 # Trace parsing utilities
│   ├── payload1.json                  # Test payloads
│   ├── payload2.json
│   ├── payload3.json
│   └── debug_trace.js
├── traces/                            # Consolidated trace files
│   ├── trace1.sse
│   ├── trace2.sse
│   └── trace3.sse
├── output/                            # Test execution outputs and coverage
├── run-e2e.mjs                        # Main frontend test runner
├── run_e2e.sh                         # Legacy shell runner  
├── run_e2e.ps1                        # Legacy PowerShell runner
├── run_backend_e2e_tests.py           # Backend E2E test runner
├── run_backend_e2e_demo.py            # Backend testing orchestrator
├── demo_fake_components.py            # Quick demo of fake components
├── BACKEND_E2E_REMAINING_ISSUES.md    # Documentation of remaining test issues
└── logs/                              # Test execution logs
```

## Backend E2E Test Status

The backend E2E test suite has achieved **89% success rate (17/19 tests passing)**:

```
✅ PASSING: 17 tests (89%)
❌ FAILING: 2 tests (11%) 
🎯 SKIPPED: 0 tests

Current Status:
- ✅ API Endpoints: Working
- ✅ Authentication: Working  
- ✅ Request/Response Validation: Working
- ✅ Deterministic Responses: Working
- ✅ Error Handling: Working (basic scenarios)
- ❌ Streaming: Not Working (complex async issues)
```

### Running Backend E2E Tests

```bash
# Run from drsearch_backend directory
cd drsearch_backend

# Simple component tests (always pass)
poetry run python ../test_full_app/run_backend_e2e_tests.py --simple-only

# Full API tests (17/19 passing)
poetry run python ../test_full_app/run_backend_e2e_tests.py --full-only

# All tests
poetry run python ../test_full_app/run_backend_e2e_tests.py
```

### Remaining Issues

Two tests are currently failing due to complex technical challenges:

1. **Error Simulation Test**: LLM initialization error simulation needs patch target investigation
2. **Streaming Format Test**: SSE streaming has async event loop conflicts in test environment

**📖 For detailed documentation** of these issues, root cause analysis, and potential solutions, see: **[BACKEND_E2E_REMAINING_ISSUES.md](./BACKEND_E2E_REMAINING_ISSUES.md)**

## Running Frontend Tests

The frontend tests can be executed using:

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