#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export LLM_SERVICE=fake
export VECTOR_BACKEND=pgvector
export PGVECTOR_URL=${PGVECTOR_URL:-"postgresql://username:password@localhost:5432/pgvector_db"}
export AUTH_ENABLED=False
export RAG_ON=True
export LOG_OUTPUT_MODE=local

cd "$ROOT_DIR/drsearch_backend"
poetry run uvicorn app:app --host 0.0.0.0 --port 8011 &
PID=$!
# wait for server
sleep 5

check() {
  if ! "$@"; then
    echo "Command failed: $*" >&2
    kill $PID
    exit 1
  fi
}

check curl -s http://localhost:8011/index-options
check curl -s -X POST http://localhost:8011/feedback -H 'Content-Type: application/json' -d '{"run_id":"11111111-1111-1111-1111-111111111111","key":"user_score","score":1}'
check curl -s -X POST http://localhost:8011/chat/stream_log -H 'Content-Type: application/json' -d '{"question":"hello"}'

kill $PID
wait $PID 2>/dev/null || true
