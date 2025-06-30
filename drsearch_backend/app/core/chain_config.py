# file: app/core/chain_config.py

"""
Chain-specific environment setup and constants for DRSearch's RAG/chat pipeline.
"""

import os
from pathlib import Path

import truststore  # ensure OS-level CA store is honoured
from dotenv import load_dotenv

# ─── Environment bootstrapping ────────────────────────────────────────────────

# Inject corporate root/intermediate certs into the SSL truststore
truststore.inject_into_ssl()

# Load .env into os.environ
load_dotenv()

# ─── Chain constants ─────────────────────────────────────────────────────────

#: Toggle RAG vs. plain-chatbot mode
RAG_ON: bool = os.getenv("RAG_ON", "True").lower() == "true"

#: Vector database backend to use ("weaviate", "pgvector", or "azure")
_VECTOR_BACKEND: str = os.getenv("VECTOR_BACKEND", "weaviate").lower()

#: Connection string for pgvector when using the PostgreSQL backend
_PGVECTOR_URL: str = os.getenv("PGVECTOR_URL", "")

#: Azure Search connection settings
_AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
_AZURE_SEARCH_KEY: str = os.getenv("AZURE_SEARCH_KEY", "")

#: How many documents to pull per query when RAG_ON
_NUMBER_OF_DOCS_RETRIEVED: int = 3

#: Default Weaviate index name
_DEFAULT_INDEX: str = "JACSKE_Program"

# NOTE: During certain unit-test scenarios we import this module **before**
# the pytest fixtures that set environment variables are executed.  Directly
# indexing ``os.environ`` would therefore raise a ``KeyError`` and break test
# collection.  We use ``os.getenv`` with a sensible default instead which
# keeps the import safe while still honouring any values that *are* present.

_WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "")
_WEAVIATE_API_KEY: str = os.getenv("WEAVIATE_API_KEY", "")

#: Whether Auth is enabled (True/False)
_AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "True") == "True"

#: Directory where part-number → file mappings CSVs live
_MAPPING_DIR: Path = Path(__file__).resolve().parent.parent / "reference_docs_mappings"
