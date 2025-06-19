#!/bin/bash
set -e

RETRY_INTERVAL=5
RETRY_TIMEOUT=300

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export LLM_SERVICE=fake
export VECTOR_BACKEND=pgvector
# export PGVECTOR_URL="${PGVECTOR_URL:-postgresql://username:password@localhost:5432/pgvector_db}"
export AUTH_ENABLED=False
export RAG_ON=True
export LOG_OUTPUT_MODE=local

cd "$ROOT_DIR/drsearch_backend"

poetry run uvicorn app:app --host 0.0.0.0 --port 8011 &
SERVER_PID=$!
# give the server time to start
sleep 5

check() {
    local cmd="$1"
    local elapsed=0
    while [ $elapsed -le $RETRY_TIMEOUT ]; do
        bash -c "$cmd"
        local exit_code=$?
        if [ $exit_code -eq 0 ]; then
            return 0
        elif [ $exit_code -eq 7 ]; then
            echo "Connection failed (exit $exit_code). Retrying in $RETRY_INTERVAL s ... (elapsed $elapsed/$RETRY_TIMEOUT)"
        elif [ $exit_code -eq 22 ]; then
            echo "HTTP error (exit $exit_code). Not retrying: $cmd" >&2
            break
        else
            echo "Command failed (exit $exit_code). Retrying in $RETRY_INTERVAL s ... (elapsed $elapsed/$RETRY_TIMEOUT)"
        fi
        sleep $RETRY_INTERVAL
        elapsed=$((elapsed + RETRY_INTERVAL))
    done
    echo "Command failed after $RETRY_TIMEOUT seconds: $cmd" >&2
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null || true
    exit 1
}

check "curl -s http://localhost:8011/index-options"

feedback_payload='{
  "run_id": "11111111-1111-1111-1111-111111111111",
  "key": "user_score",
  "score": 1,
  "feedback_id": "22222222-2222-2222-2222-222222222222",
  "comment": "Helpful response.",
  "conversation": [
    {"human": "What\u2019s the part number?", "ai": "It\u0027s ABC123."},
    {"human": "Thanks", "ai": "You\u0027re welcome!"}
  ],
  "documents": ["doc1", "doc2"]
}'
feedback_file=$(mktemp)
echo "$feedback_payload" > "$feedback_file"
check "curl -s -X POST http://localhost:8011/feedback -H 'Content-Type: application/json' --data-binary @$feedback_file"

chat_payload='{
  "input": {
    "question": "What is the BOM for unit XYZ?",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"},
      {"human": "Tell me about XYZ", "ai": "XYZ is a system..."}
    ],
    "index_name": "test_docs",
    "num_docs_retrieved": 3
  }
}'
chat_file=$(mktemp)
echo "$chat_payload" > "$chat_file"
check "curl -s -X POST http://localhost:8011/chat/stream_log -H 'Content-Type: application/json' --data-binary @$chat_file"

kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true
rm -f "$feedback_file" "$chat_file"
