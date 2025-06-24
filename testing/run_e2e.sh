#!/bin/bash
set -euo pipefail

uvicorn testing.simulator:app --port 8011 --reload > simulator.log 2>&1 &
SIM_PID=$!

pushd drsearch_frontend >/dev/null
yarn install --silent
API_BASE_URL=http://localhost:8011 yarn dev -p 3000 > ../frontend.log 2>&1 &
FRONT_PID=$!
popd >/dev/null

for i in {1..30}; do
  curl -s http://localhost:8011/last_request >/dev/null 2>&1 && break
  sleep 1
done
for i in {1..30}; do
  curl -s http://localhost:3000 >/dev/null 2>&1 && break
  sleep 1
done

npx playwright install --with-deps
npx playwright test testing/e2e.spec.ts
STATUS=$?

kill $FRONT_PID $SIM_PID || true
exit $STATUS
