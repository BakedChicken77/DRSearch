# PGvector Fake Data Testing

This guide explains how to load fake data into the PGvector database and verify that the backend works using the fake LLM service.

## 1. Load Fake PGvector Data

1. Ensure PostgreSQL with the PGvector extension is running.
2. Modify connection variables in `load_pgvector_data.sh` if necessary.
3. Run the script:

```bash
bash codex_environment_setup_scripts/load_pgvector_data.sh
```

This reads `fake_pgvector_docs.jsonl` and inserts deterministic embeddings into the `langchain_pg_embedding` table.

## 2. Start the Backend with Fake Services

Use the provided helper script to start the backend with `LLM_SERVICE=fake` and to hit the key endpoints:

```bash
bash codex_environment_setup_scripts/test_backend.sh
```

The script sets environment variables, starts `uvicorn` on port `8011`, and performs requests against `/index-options`, `/feedback`, and `/chat/stream_log`.

## 3. Customizing the Fake Documents

Edit `fake_pgvector_docs.jsonl` before running the loader if you want to adjust the test data. Each line should contain a JSON object with `document` text and accompanying `metadata`.
