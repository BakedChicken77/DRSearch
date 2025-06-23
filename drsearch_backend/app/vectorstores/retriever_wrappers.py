
from typing import Any, Callable, Iterable
import logging

from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)


class LoggedRetriever(BaseRetriever):
    model_config = {"arbitrary_types_allowed": True}
    _base: BaseRetriever = PrivateAttr()

    def __init__(self, base: BaseRetriever):
        super().__init__()
        self._base = base

    def _get_relevant_documents(self, query: str, *, run_manager=None):
        docs = self._base.get_relevant_documents(query)
        logger.info(
            "retriever returned %d documents",
            len(docs),
            extra={"query": query, "doc_count": len(docs)},
        )
        return docs

    async def _aget_relevant_documents(self, query: str, *, run_manager=None):
        docs = await self._base.ainvoke(query)
        logger.info(
            "retriever returned %d documents",
            len(docs),
            extra={"query": query, "doc_count": len(docs)},
        )
        return docs


class FilteredLoggedRetriever(LoggedRetriever):
    def __init__(self, base: BaseRetriever, allowed_metadata_keys: Iterable[str]):
        super().__init__(base)
        self.allowed = set(allowed_metadata_keys)

    def _strip(self, docs):
        for doc in docs:
            doc.metadata = {k: v for k, v in doc.metadata.items() if k in self.allowed}
        return docs

    def _get_relevant_documents(self, query: str, *, run_manager=None):
        docs = super()._get_relevant_documents(query, run_manager=run_manager)
        return self._strip(docs)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None):
        docs = await super()._aget_relevant_documents(query, run_manager=run_manager)
        return self._strip(docs)
