#!/bin/bash
set -e
cd "$(dirname "$0")/.." # project root

export PGVECTOR_URL="postgresql://username:password@localhost:5432/pgvector_db"
export VECTOR_BACKEND="pgvector"
export RAG_ON="True"
export LLM_SERVICE="fake"
export AUTH_ENABLED="False"

poetry run uvicorn app:app --host 0.0.0.0 --port 8011 &
PID=$!
sleep 5

status=$(curl -s -o /tmp/index.json -w "%{http_code}" http://localhost:8011/index-options)
if [ "$status" != "200" ]; then echo "index-options failed"; kill $PID; exit 1; fi

chat_status=$(curl -s -o /tmp/chat.log -w "%{http_code}" -H "Content-Type: application/json" -d '{"input":{"question":"hello"}}' http://localhost:8011/chat/stream_log)
if [ "$chat_status" != "200" ]; then echo "chat failed"; kill $PID; exit 1; fi

fb_status=$(curl -s -o /tmp/fb.json -w "%{http_code}" -H "Content-Type: application/json" -d '{"run_id":"11111111-1111-1111-1111-111111111111","key":"user_score","score":1}' http://localhost:8011/feedback)
if [ "$fb_status" != "200" ]; then echo "feedback failed"; kill $PID; exit 1; fi

kill $PID
sleep 2

echo "All backend endpoint checks passed"
