#!/bin/bash
# Backup script to restore the old E2E test structure if needed

echo "Restoring old E2E test structure..."

# Restore backend files
mkdir -p drsearch_backend/testing_full_app/traces
cp test_full_app/backend/simulator.py drsearch_backend/testing_full_app/
cp test_full_app/backend/__init__.py drsearch_backend/testing_full_app/
cp test_full_app/backend/create_test_traces.ps1 drsearch_backend/testing_full_app/
cp test_full_app/traces/*.sse drsearch_backend/testing_full_app/traces/

# Restore frontend files
mkdir -p drsearch_frontend/testing_full_app/traces
cp test_full_app/frontend/*.spec.ts drsearch_frontend/testing_full_app/
cp test_full_app/frontend/trace_utils.ts drsearch_frontend/testing_full_app/
cp test_full_app/frontend/payload*.json drsearch_frontend/testing_full_app/
cp test_full_app/frontend/debug_trace.js drsearch_frontend/testing_full_app/
cp test_full_app/traces/*.sse drsearch_frontend/testing_full_app/traces/

# Update paths in restored files
sed -i '' 's|../traces|../../drsearch_backend/testing_full_app/traces|g' drsearch_frontend/testing_full_app/e2e.spec.ts
sed -i '' 's|../traces|../../drsearch_backend/testing_full_app/traces|g' drsearch_frontend/testing_full_app/e2e_negative.spec.ts
sed -i '' 's|../traces|../../drsearch_backend/testing_full_app/traces|g' drsearch_frontend/testing_full_app/debug_trace.js
sed -i '' 's|parent.parent|parent|g' drsearch_backend/testing_full_app/simulator.py

echo "Old structure restored. You may need to update run-e2e.mjs to use the old paths." 