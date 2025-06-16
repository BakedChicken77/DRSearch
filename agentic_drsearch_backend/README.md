## Agentic DR-Search Backend

A drop-in replacement for `drsearch_backend` built on **OpenAI Agents** and **pgvector**.

### Quick start (Docker)
#### Run Locally
```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8011 
```
#### Run in Container
```bash
# 1. Build & run
docker compose up --build
# 2. Open docs (non-prod) at http://localhost:8000/docs
```

Ingesting documents
```bash
docker compose exec backend python -m app.ingestion.ingest /data/raw_docs
```

Endpoints (v1)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | /api/v1/query | Ask a question |
| POST | /api/v1/feedback | Submit answer feedback |
| GET | /api/v1/index-options | List vector indexes |
| GET | /api/v1/files/{filename} | Download source doc |

---

**Everything above is ready to drop into a repo, build, and run.**  
Fill in any business-specific logic (advanced chunking, additional tools, authentication, etc.) as needed, and the frontend will continue to work unchanged.
