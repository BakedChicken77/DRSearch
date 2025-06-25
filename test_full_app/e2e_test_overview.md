# DRSearch End-to-End Test Harness

This document provides a comprehensive overview of the full application test suite located under `test_full_app`. It explains how the Node.js harness launches the simulator and frontend, describes the test scenarios, and outlines how coverage and logs are produced.

## Purpose

The goal of the end-to-end (E2E) tests is to validate that the DRSearch frontend properly interacts with the backend API. A small FastAPI application simulates server behaviour by replaying pre-recorded Server-Sent Events (SSE) traces. Playwright drives the browser to reproduce typical user flows and verify error handling.

## Directory Layout

```
test_full_app/
├── run-e2e.mjs          # Cross‑platform Node.js harness
├── run_e2e.ps1          # Legacy Windows PowerShell runner
├── run_e2e.sh           # Legacy Bash runner
└── logs/                # Created automatically to store run logs
```

Related files:

```
drsearch_backend/testing_full_app/
  simulator.py          # FastAPI simulator used by the tests
  traces/               # `.sse` files returned as SSE streams

drsearch_frontend/testing_full_app/
  e2e.spec.ts           # Happy‑path Playwright tests
  e2e_negative.spec.ts  # Failure scenario tests
  payload*.json         # Expected request bodies for happy‑path tests
  trace_utils.ts        # Helper for parsing `.sse` traces
```

## Node.js Test Harness (`run-e2e.mjs`)

The script `test_full_app/run-e2e.mjs` fully replaces the old shell script. Its responsibilities include:

1. **Dynamic Port Allocation** – two free TCP ports are chosen at runtime, one for the backend simulator and one for the frontend dev server.
2. **Starting the Simulator** – `poetry run uvicorn testing_full_app.simulator:app` is spawned in `drsearch_backend` with the chosen port. Output is logged to `test_full_app/logs/simulator1.*.log`.
3. **Installing Frontend Dependencies (if needed)** – `yarn install --silent` is only executed when `node_modules` is missing to speed up CI runs.
4. **Starting the Next.js Dev Server** – `yarn dev --port <port>` runs in `drsearch_frontend`, pointing `API_BASE_URL` at the simulator. Logs are written to `frontend1.*.log`.
5. **Readiness Polling** – the script repeatedly attempts to fetch `/index-options` from the backend and the root page of the frontend until both respond or a timeout (60 s) is hit.
6. **Running Playwright Tests** – `npx playwright test testing_full_app` executes all specs. When `COLLECT_COVERAGE=1` is present, the environment variable `PW_TEST_COVERAGE=1` is forwarded so coverage data is emitted.
7. **Cleanup** – all child processes are terminated when the test run finishes or the script receives `SIGINT`/`SIGTERM`. The exit code of Playwright is used as the script’s exit code.

The harness is fully cross‑platform and works on Linux (bash) and Windows (PowerShell) by simply running:

```bash
node test_full_app/run-e2e.mjs
```

Logs for each run accumulate under `test_full_app/logs/`.

## Backend Simulator

`drsearch_backend/testing_full_app/simulator.py` serves two endpoints used by the tests:

- `GET /index-options` – returns five index definitions:
  - `TEST_INDEX`
  - `OTHER_INDEX`
  - `ERROR_500`
  - `SLOW_STREAM`
  - `MALFORMED_SSE`
- `POST /chat/stream_log` – streams back one of the trace files as SSE. Special behaviours are triggered by the `index_name` in the request:
  - `ERROR_500` &rarr; immediate HTTP 500 with `{"detail": "backend failure"}`.
  - `SLOW_STREAM` &rarr; emits each line with a configurable delay (default 0.1 s).
  - `MALFORMED_SSE` &rarr; randomly inserts lines that are not valid SSE.
  - `TEST_INDEX` and `OTHER_INDEX` &rarr; return normal traces with no delay.

During tests the simulator records the most recent request at `/last_request` to aid debugging.

## Trace Parsing Helper

`drsearch_frontend/testing_full_app/trace_utils.ts` exports `extractFinalOutput(tracePath: string)`. It reads every `data: { … }` line of an `.sse` trace file and returns the final `value.output` from an op whose `path` ends with `final_output`. If no such entry is present, an error is thrown. This helper allows the Playwright tests to assert against the exact output expected from each trace.

## Playwright Test Suites

### Happy Path (`e2e.spec.ts`)

Three payload files (`payload1.json`, `payload2.json`, `payload3.json`) describe the expected request bodies. For each payload, the test performs the following steps:

1. Navigate to the frontend base URL provided by the harness.
2. Wait for the index dropdown to be populated, then select the payload’s index.
3. If the payload requires fewer than three documents, the settings drawer is opened via `button[aria-label="Open settings"]` and the value is changed.
4. Fill the question into the chat input and click the send button.
5. Intercept the request to `POST /chat/stream_log` and assert the JSON body matches the payload exactly.
6. Wait for the chat stream area to include the last 20 characters of the trace’s final output (derived using `extractFinalOutput`). No fixed sleeps are used.
7. Assert that no JavaScript console errors were emitted.

### Negative Path (`e2e_negative.spec.ts`)

This suite exercises failure scenarios:

1. **ERROR_500** – After selecting the `ERROR_500` index and sending a question, the page should display a user‑facing error matching `/backend failure/i`.
2. **SLOW_STREAM** – Using the `SLOW_STREAM` index, the test waits up to 30 s for the streamed response to complete and verifies it ends with the expected text from `trace3.sse`.
3. **MALFORMED_SSE** – When random garbage lines are injected, the UI should still display streamed output and no uncaught console errors should occur.

A helper function within the spec handles the common setup of navigating to the page, selecting an index via `data-testid="index-select"`, filling the question, and sending it.

## Coverage

Setting the environment variable `COLLECT_COVERAGE=1` when invoking the harness enables Playwright’s coverage reporting. The resulting coverage files are emitted in the default Playwright output directory inside `drsearch_frontend`.

Example:

```bash
COLLECT_COVERAGE=1 node test_full_app/run-e2e.mjs
```

## Cleaning Up

The harness ensures that all spawned processes (simulator and dev server) are terminated even if the test run fails or is interrupted with Ctrl‑C. Ports allocated during the run are released automatically.

## Summary

The end‑to‑end test harness allows DRSearch to verify both normal and erroneous interactions between the frontend and the backend. It is designed to run identically on Linux and Windows and integrates seamlessly with CI environments.
