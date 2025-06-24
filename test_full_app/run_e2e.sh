#!/bin/bash
set -euo pipefail

cleanup() {
  kill "$FRONT_PID" 2>/dev/null || true
  kill "$SIM_PID" 2>/dev/null || true
  fuser -k 3000/tcp 2>/dev/null || true
  fuser -k 8011/tcp 2>/dev/null || true
}
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

SIM_OUT_LOG="$LOG_DIR/simulator1.out.log"
SIM_ERR_LOG="$LOG_DIR/simulator1.err.log"
FRONT_OUT_LOG="$LOG_DIR/frontend1.out.log"
FRONT_ERR_LOG="$LOG_DIR/frontend1.err.log"

export AUTH_ENABLED="False"
export NEXT_PUBLIC_AUTH_ENABLED="False"

cd "$SCRIPT_DIR/.."

# Start backend simulator
(cd drsearch_backend && poetry run uvicorn testing_full_app.simulator:app --port 8011 >"$SIM_OUT_LOG" 2>"$SIM_ERR_LOG" & echo $! > "$LOG_DIR/sim.pid")
SIM_PID=$(cat "$LOG_DIR/sim.pid")

# Start frontend
(cd drsearch_frontend && yarn install --silent && API_BASE_URL="http://localhost:8011" yarn dev --port 3000 >"$FRONT_OUT_LOG" 2>"$FRONT_ERR_LOG" & echo $! > "$LOG_DIR/front.pid")
FRONT_PID=$(cat "$LOG_DIR/front.pid")

# Wait for servers to be ready
for i in {1..60}; do
  if curl -sf "http://localhost:8011/index-options" >/dev/null 2>&1 && curl -sf "http://localhost:3000" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd drsearch_frontend

npx -y playwright install --with-deps

npx -y playwright test testing_full_app/e2e.spec.ts
STATUS=$?

# Cleanup processes
kill "$FRONT_PID" 2>/dev/null || true
kill "$SIM_PID" 2>/dev/null || true
sleep 1
# Extra safety net: kill anything still bound to ports
fuser -k 3000/tcp 2>/dev/null || true
fuser -k 8011/tcp 2>/dev/null || true

exit $STATUS
