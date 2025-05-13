# file: app/chain/embeddings.py

from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_openai import AzureOpenAIEmbeddings

logger = logging.getLogger(__name__)


class EmbeddingFactory:
    """Singleton provider for the Azure OpenAI embedding model."""

    _instance: Optional[AzureOpenAIEmbeddings] = None

    @classmethod
    def get(cls) -> AzureOpenAIEmbeddings:
        """Return a cached embedding model instance (create if necessary)."""
        if cls._instance is None:
            logger.info("Instantiating embedding model")
            cls._instance = AzureOpenAIEmbeddings(
                model=os.environ["AZURE_OPENAI_EMBEDDER"],
                chunk_size=200,
                api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            )
        return cls._instance
