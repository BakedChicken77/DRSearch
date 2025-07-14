# DRSearch Backend LangGraph

This module implements a simple RAG backend using FastAPI, LangGraph, PostgreSQL with pgvector, Redis, and Azure OpenAI. A Streamlit frontend communicates with the API.

## Setup

```bash
cd drsearch_backend_lg
poetry install
cp .env.example .env
```
Edit `.env` with your settings.

### Running with Docker

```bash
docker-compose up --build
```

### Running locally

```bash
poetry run uvicorn app.main:app --reload
```

### Tests

```bash
poetry run pytest -q
```
