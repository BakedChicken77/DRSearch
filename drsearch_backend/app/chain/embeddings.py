# file: app/chain/embeddings.py

from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_openai import AzureOpenAIEmbeddings
from langchain.embeddings.base import Embeddings
import hashlib
import random

logger = logging.getLogger(__name__)


class EmbeddingFactory:
    """Singleton provider for the embedding model."""

    _instance: Optional[Embeddings] = None

    @classmethod
    def get(cls) -> Embeddings:
        """Return a cached embedding model instance (create if necessary)."""
        if cls._instance is None:
            service = os.getenv("LLM_SERVICE", "azure").lower()
            logger.info("Instantiating embedding model")
            if service == "fake":

                class FakeEmbedder(Embeddings):
                    def _embed(self, text: str) -> list[float]:
                        rnd = random.Random(
                            int(hashlib.md5(text.encode()).hexdigest(), 16)
                        )
                        return [rnd.random() for _ in range(1536)]

                    def embed_query(self, text: str) -> list[float]:
                        return self._embed(text)

                    def embed_documents(self, texts):
                        return [self._embed(t) for t in texts]

                cls._instance = FakeEmbedder()
            else:
                cls._instance = AzureOpenAIEmbeddings(
                    model=os.environ["AZURE_OPENAI_EMBEDDER"],
                    chunk_size=200,
                    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
                )
        return cls._instance
