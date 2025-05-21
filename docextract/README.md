Here's a cleaned-up and professional version of your `README.md` content with consistent formatting, clear instructions, and better structure:

---

````markdown
# docextract

`docextract` is a document ingestion service built with **FastAPI** and **Python 3.11**. It provides a complete pipeline to partition DOCX/PDF files, generate embeddings, enrich metadata using OpenAI models, and index vectors into Weaviate, while tracking document states in PostgreSQL.

The service includes:
- A FastAPI backend
- A minimal HTML GUI for triggering ingestion
- Docker-based deployment with optional GPU support

---

## 🧪 Quick Start

### Prerequisites
Ensure the following containers are running before using the GUI:
- **Weaviate**
- **PostgreSQL**

> ⚠️ These are **not** required when using the `/run-script/` API endpoint directly.

---

### 1️⃣ Build the Ingest Container
```powershell
docker-compose -f docker-compose.ingest.yml build --no-cache
````

> ⏱️ Note: The image is approximately **40 GB**, so the build will take some time.

---

### 2️⃣ Start the Containers

```powershell
docker-compose -f docker-compose.ingest.yml up -d
```

---

### 3️⃣ Access the GUI

Navigate to: [http://localhost:8000/gui/](http://localhost:8000/gui/)

> 🗂️ Any files placed in the `.\doc` folder will be mounted into the container and ingested when the "Ingest" button is clicked in the GUI.

---

## 🧠 Using the Ingest API

If you're calling the ingest API directly (e.g., from `My_Python_Libraries\text_extractor`):

* Use the `/run-script/` endpoint.
* Weaviate and PostgreSQL are not required.
* The API returns raw **text**, **metadata**, and **embeddings** in the response instead of persisting them to databases.

---

## 🧩 Architecture Overview

### FastAPI Service

**File:** `main.py`

* Exposes endpoints for running ingestion, streaming logs, serving the GUI, and extracting text.
* Background tasks run `run_ingest.py` or `ingest_docs.py`.

### Ingestion Flow

**File:** `run_ingest.py`

* Parses CLI arguments (e.g., namespace, chunk size).
* Calls `process_documents()` in `partition_pdf_and_docx_Final5.py`.

### Document Processing

**File:** `partition_pdf_and_docx_Final5.py`

* Loads environment variables and sets up logging.
* Partitions documents using Unstructured.
* Cleans metadata, extracts images, and outputs chunks to JSON/text for indexing.

### Record Management

**File:** `ExtendedSQLRecordManager4.py`

* Extends LangChain’s `SQLRecordManager`.
* Tracks document status and manages record updates in batches.

### Utility Functions

**File:** `ingestion_utilities.py`

* Embedding setup, logging tools, image processing, and data cleanup.

### Acronym Processing

**File:** `Acronym_Tools.py`

* Extracts and validates acronym tables.
* Replaces acronyms in text and appends definitions to metadata.

### HTML Summarization

**File:** `HTML_Processing.py`

* Summarizes HTML fragments using OpenAI.
* Extracts titles and categorizes tables.

### Weaviate Schema

**File:** `Weaviate_Schema.py`

* Creates or updates schema classes in Weaviate.
* Supports tokenization and metadata mapping.

---

## 🐳 Dockerized Deployment

### Dockerfile: `Dockerfile.ingest`

* Multi-stage build using Poetry for dependency management.
* Adds CA certificates and library patches.
* Sets up the FastAPI runtime environment.

### Compose File: `docker-compose.ingest.yml`

* Spins up the `docextract` service.
* Supports GPU acceleration.
* Watches for source code changes.

---

## 🖥️ Static GUI

**File:** `static/index.html`

* Lightweight UI with basic JavaScript.
* Triggers ingestion via `/run-script/` or `/ingest-new-docs/{collection}`.
* Streams log output in real time.

---

## ✅ Summary

`docextract` is a dockerized ingestion engine that:

* Converts unstructured documents into structured vector embeddings.
* Enhances metadata via OpenAI summarization and acronym resolution.
* Indexes enriched chunks into Weaviate.
* Tracks ingestion state in PostgreSQL.
* Supports both GUI-based and programmatic ingestion.

Perfect for building intelligent search and retrieval systems from semi-structured document repositories.

```

Let me know if you'd like to include usage examples (e.g., `curl` commands), environment variable references, or architecture diagrams.
```
