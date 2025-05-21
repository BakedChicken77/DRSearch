# file: app/chain/engine.py

from __future__ import annotations

import logging
import os
from operator import itemgetter
from typing import Callable, List, Sequence

from langchain.prompts import (ChatPromptTemplate, MessagesPlaceholder,
                               PromptTemplate)
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.schema import Document
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.retriever import BaseRetriever
from langchain.schema.runnable import (Runnable, RunnableBranch,
                                       RunnableLambda, RunnableMap)
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI

from app import System_Prompts
from app.chain.exceptions import ConfigurationError
from app.chain.formatter import DocumentFormatter
from app.chain.history import HistorySerializer
from app.chain.mapping import PartNumberMapping
from app.chain.retriever import RetrieverFactory
from app.core.chain_config import _DEFAULT_INDEX, RAG_ON
from app.index_config import INDEX_CONFIG

logger = logging.getLogger(__name__)


class ChatEngine:
    """High-level orchestrator – builds runnable chains on demand."""

    def __init__(self, index_name: str = _DEFAULT_INDEX) -> None:
        self._index_name = index_name
        self._cfg = INDEX_CONFIG.get(index_name)
        if self._cfg is None:
            raise ConfigurationError(f"Unknown index '{index_name}'")
        self._mapping = PartNumberMapping(self._cfg["PN_TO_FILE_MAPPING"])
        self._llm = self._init_llm()
        self._answer_chain = self._build_answer_chain()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def answer_chain(self) -> Runnable:
        """Return the fully-wired runnable chain."""
        return self._answer_chain

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _init_llm() -> BaseLanguageModel:
        """Instantiate Azure Chat completion model (singleton per process)."""
        try:
            logger.info("Creating AzureChatOpenAI model")
            return AzureChatOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.environ["AZURE_OPENAI_API_VERSION"],
                temperature=0.0,
                model=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
                streaming=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to initialise LLM: %s", exc)
            raise

    # ------------------------------------------------------------------

    def _build_answer_chain(self) -> Runnable:
        """Wire together *langchain* components according to current mode."""
        cfg = self._cfg
        response_template: str = (
            self._cfg["response_template"] if not RAG_ON else cfg["response_template"]
        )

        retriever: BaseRetriever | None = None
        raw_retriever: BaseRetriever | None = None
        format_docs_fn: Callable[[Sequence[Document]], str] | None = None

        enable_retrieval = False
        if RAG_ON:
            try:
                retriever = RetrieverFactory.build(self._index_name)
                raw_retriever = RetrieverFactory.build(self._index_name)
                format_docs_fn = DocumentFormatter(self._mapping)
                enable_retrieval = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to initialise retriever – running without RAG: %s",
                    exc,
                )
        else:
            logger.info("Running in chatbot-only mode – retrieval disabled")

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", response_template),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}"),
            ]
        )

        if enable_retrieval and raw_retriever is not None:
            # decomposer_prompt = PromptTemplate.from_template(System_Prompts.REPHRASE_TEMPLATE)
            retriever = MultiQueryRetriever.from_llm(
                retriever=raw_retriever,
                llm=self._llm,
                include_original=True,
                prompt=self._cfg["DECOMPOSER"],
            )
        else:
            retriever = None

        if enable_retrieval and retriever and format_docs_fn:
            retriever_chain = self._build_retriever_chain(
                retriever, format_docs_fn
            ).with_config(run_name="FindDocs")
            context_map = RunnableMap(
                {
                    "context": retriever_chain,
                    "question": itemgetter("question"),
                    "chat_history": itemgetter("chat_history"),
                }
            )
        else:
            context_map = RunnableMap(
                {
                    "context": RunnableLambda(lambda _: ""),
                    "question": itemgetter("question"),
                    "chat_history": itemgetter("chat_history"),
                }
            )

        final_step = (prompt | self._llm | StrOutputParser()).with_config(
            streaming=True
        )

        chain: Runnable = (
            {
                "question": RunnableLambda(itemgetter("question")),
                "chat_history": RunnableLambda(HistorySerializer()),
            }
            | context_map
            | final_step
        )
        return chain

    # ------------------------------------------------------------------

    def _build_retriever_chain(
        self,
        retriever: BaseRetriever,
        format_docs: Callable[[Sequence[Document]], str],
    ) -> Runnable:
        """Return retriever chain that supports follow-up questions."""
        condense_prompt = PromptTemplate.from_template(System_Prompts.REPHRASE_TEMPLATE)
        condense = condense_prompt | self._llm | StrOutputParser()

        def _modify_docs(docs: List[Document]) -> List[Document]:
            # Enrich docs with UNC path when mapping present
            mapping = self._mapping.data
            if mapping is None:
                return docs
            for doc in docs:
                filename = doc.metadata.get("filename", "")
                if filename in mapping:
                    doc.metadata["file_path"] = mapping[filename]
            return docs

        base_chain = condense | retriever | RunnableLambda(_modify_docs)
        history_branch = (
            RunnableLambda(lambda d: bool(d.get("chat_history"))),
            base_chain,
        )
        no_history_branch = (
            RunnableLambda(itemgetter("question"))
            | retriever
            | RunnableLambda(_modify_docs)
        )
        return RunnableBranch(history_branch, no_history_branch)  # type: ignore[attr-defined]
