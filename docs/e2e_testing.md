# End-to-End Testing

DRSearch uses end-to-end (E2E) tests to validate the complete user experience from frontend to backend. The test suite is located in `test_full_app/` and includes:

- **Backend simulator**: `test_full_app/backend/simulator.py` exposes minimal endpoints used during testing. It streams predefined Server‑Sent Events (SSE) traces and serves available index options.
- **Playwright tests**: `test_full_app/frontend/e2e.spec.ts` drives the browser to exercise the UI and verify the requests sent to the simulator.
- **Payload files**: `test_full_app/frontend/payload1.json`, `payload2.json`, and `payload3.json` contain the expected request bodies used by the tests.
- **Trace files**: located in `test_full_app/traces/` and loaded by the simulator to emulate backend responses.

## Test Execution

The E2E tests are executed using the Node.js harness:

```bash
COLLECT_COVERAGE=1 node test_full_app/run-e2e.mjs
```

This command:

1. Starts the FastAPI simulator on a dynamic port.
2. Launches the Next.js development server pointing to the simulator.
3. Waits for both services to be ready.
4. Executes the Playwright test `test_full_app/frontend/e2e.spec.ts`.

## Test Coverage

When `COLLECT_COVERAGE=1` is set, the test harness enables Playwright's coverage reporting. Coverage data is collected and stored in `test_full_app/output/<timestamp>/` for later analysis.

## Troubleshooting

For detailed troubleshooting information, see `test_full_app/TROUBLESHOOTING.md`.
