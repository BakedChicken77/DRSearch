#!/usr/bin/env bash
set -euo pipefail

SIM_LOG=simulator.log
FRONT_LOG=frontend.log

uvicorn testing.simulator:app --port 8011 --reload > "$SIM_LOG" 2>&1 &
SIM_PID=$!

pushd drsearch_frontend >/dev/null
yarn install --silent
API_BASE_URL=http://localhost:8011 yarn dev --port 3000 > ../"$FRONT_LOG" 2>&1 &
FRONT_PID=$!
popd >/dev/null

for i in {1..60}; do
  if curl -s http://localhost:8011/index-options >/dev/null 2>&1 && curl -s http://localhost:3000 >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

npx playwright install --with-deps
npx playwright test testing/e2e.spec.ts
STATUS=$?
kill $FRONT_PID $SIM_PID
exit $STATUS
