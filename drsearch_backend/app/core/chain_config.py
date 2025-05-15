# file: app/core/chain_config.py

"""
Chain-specific environment setup and constants for DRSearch’s RAG/chat pipeline.
"""

import os
from pathlib import Path

import truststore   # ensure OS-level CA store is honoured
from dotenv import load_dotenv

# ─── Environment bootstrapping ────────────────────────────────────────────────

# Inject corporate root/intermediate certs into the SSL truststore
truststore.inject_into_ssl()

# Load .env into os.environ
load_dotenv()

# ─── Chain constants ─────────────────────────────────────────────────────────

#: Toggle RAG vs. plain-chatbot mode
RAG_ON: bool = True

#: How many documents to pull per query when RAG_ON
_NUMBER_OF_DOCS_RETRIEVED: int = 3

#: Default Weaviate index name
_DEFAULT_INDEX: str = "JACSKE_Program"

#: Weaviate connection settings
_WEAVIATE_URL: str = os.environ["WEAVIATE_URL"]
_WEAVIATE_API_KEY: str = os.environ["WEAVIATE_API_KEY"]

#: Whether Auth is enabled (True/False)
_AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "True") == "True"

#: Directory where part-number → file mappings CSVs live
_MAPPING_DIR: Path = Path(__file__).resolve().parent.parent / "reference_docs_mappings"
