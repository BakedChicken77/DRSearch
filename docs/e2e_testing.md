# End-to-End Testing

This document explains how the `test_full_app/run_e2e.sh` script executes the end-to-end tests for the DRSearch application.

## Overview

The end-to-end test suite verifies request and response handling between the frontend and a simulated backend. It uses Playwright to automate the browser and a small FastAPI app to replay recorded traces.

## Components

- **Backend simulator**: `drsearch_backend/testing_full_app/simulator.py` exposes minimal endpoints used during testing. It streams predefined Server‑Sent Events (SSE) traces and serves available index options.
- **Playwright tests**: `drsearch_frontend/testing_full_app/e2e.spec.ts` drives the browser to exercise the UI and verify the requests sent to the simulator.
- **Payload files**: `drsearch_frontend/testing_full_app/payload1.json`, `payload2.json`, and `payload3.json` contain the expected request bodies used by the tests.
- **Trace files**: located in `drsearch_backend/testing_full_app/traces/` and loaded by the simulator to emulate backend responses.
- **Runner script**: `test_full_app/run_e2e.sh` starts both the simulator and the Next.js frontend, then launches the Playwright tests.

## Running the Tests

```bash
bash test_full_app/run_e2e.sh
```

The script performs the following steps:

1. Starts the FastAPI simulator on port 8011.
2. Launches the frontend on port 3000 with authentication disabled.
3. Waits for both services to become available.
4. Executes the Playwright test `testing_full_app/e2e.spec.ts`.
5. Shuts down all processes and cleans up open ports.

Logs from both services are written to `test_full_app/logs/` during the run.

## What the Tests Cover

For each payload file, the Playwright test:

1. Intercepts the request to `/chat/stream_log` and checks that the request `input` matches the payload.
2. Selects the appropriate index option in the UI.
3. Opens the settings drawer when necessary and updates the number of documents to retrieve.
4. Sends the question and waits briefly for a response.

Any console errors captured during the run cause the test to fail.

## Dependencies

The tests rely on Node.js dependencies from `drsearch_frontend` and Python dependencies installed via Poetry for `drsearch_backend`.
