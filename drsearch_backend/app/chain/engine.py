# drsearch_backend/app/chain/engine.py

from __future__ import annotations

import logging
import os
from operator import itemgetter
from typing import Any, Callable, List, Sequence

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.schema import Document
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.retriever import BaseRetriever
from langchain.schema.runnable import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnableMap,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI
# from langchain.llms.fake import FakeStreamingListLLM
from langchain_community.llms.fake import FakeStreamingListLLM

from app import System_Prompts
from app.chain.formatter import DocumentFormatter
from app.chain.history import HistorySerializer
from app.chain.mapping import PartNumberMapping
from app.chain.retriever import RetrieverFactory
from app.core.chain_config import _DEFAULT_INDEX, RAG_ON
from app.index_config import INDEX_CONFIG

logger = logging.getLogger(__name__)


# ─── Minimal tracing helper to ensure retrieval shows in Langfuse ─────────────
def _json_safe(o: Any) -> Any:
    try:
        import json

        json.dumps(o)
        return o
    except Exception:
        return str(o)


def _trace_retriever(retriever: BaseRetriever) -> Runnable:
    """Wrap a retriever so we explicitly emit a 'RetrieveDocs' span if a Langfuse
    callback handler is present in the LCEL config. No hard dependency on Langfuse."""
    def _run(query: str, config: dict | None = None):
        config = config or {}
        raw = config.get("callbacks")
        # Extract potential handlers from LCEL callback manager or list
        if raw is None:
            handlers = []
        elif isinstance(raw, list):
            handlers = raw
        else:
            handlers = getattr(raw, "handlers", getattr(raw, "callbacks", [])) or []

        lf = None
        for cb in handlers:
            # Look for an object that exposes lf.trace.span(...)
            trace = getattr(cb, "trace", None)
            if trace is not None and hasattr(trace, "span"):
                lf = cb
                break

        span = None
        if lf is not None:
            try:
                span = lf.trace.span(name="RetrieveDocs", input={"query": query})
            except Exception:
                span = None

        try:
            docs = retriever.invoke(query, config=config)
        except Exception as exc:
            if span is not None:
                try:
                    span.end(level="ERROR", status_message=str(exc))
                except Exception:
                    pass
            raise

        if span is not None:
            try:
                span.end(
                    output=[
                        {
                            "page_content": d.page_content,
                            "metadata": {k: _json_safe(v) for k, v in d.metadata.items()},
                        }
                        for d in docs
                    ]
                )
            except Exception:
                try:
                    span.end()
                except Exception:
                    pass
        return docs

    return RunnableLambda(_run).with_config(run_name="RetrieveDocs")


class ChatEngine:
    """High-level orchestrator – builds runnable chains on demand."""

    def __init__(self, index_name: str = _DEFAULT_INDEX) -> None:
        self._index_name = index_name
        self._cfg = INDEX_CONFIG.get(index_name)
        if self._cfg is None:
            logger.warning(
                "Unknown index '%s' – running in chatbot-only mode", index_name
            )
            self._cfg = {
                "response_template": System_Prompts.RESPONSE_TEMPLATE_CHATBOT,
                "PN_TO_FILE_MAPPING": None,
                "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            }
            self._unknown_index = True
        else:
            self._unknown_index = False
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
        """Instantiate the configured language model."""
        llm_service = os.getenv("LLM_SERVICE", "azure").lower()
        try:
            if llm_service == "fake":
                logger.info("Creating FakeStreamingListLLM model")
                return FakeStreamingListLLM(responses=["fake response"])
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
            cfg["response_template"]
            if RAG_ON
            else System_Prompts.RESPONSE_TEMPLATE_CHATBOT
        )

        retriever: BaseRetriever | None = None
        raw_retriever: BaseRetriever | None = None
        format_docs_fn: Callable[[Sequence[Document]], str] | None = None

        enable_retrieval = False
        if RAG_ON and not getattr(self, "_unknown_index", False):
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
                response_template = System_Prompts.RESPONSE_TEMPLATE_CHATBOT
                enable_retrieval = False
        elif RAG_ON and getattr(self, "_unknown_index", False):
            logger.warning(
                "Index '%s' not configured – retrieval disabled", self._index_name
            )
            response_template = System_Prompts.RESPONSE_TEMPLATE_CHATBOT
            enable_retrieval = False
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
            # Ensure retrieval step is explicitly traced in Langfuse
            retriever = _trace_retriever(retriever)
        else:
            retriever = None

        if enable_retrieval and retriever and format_docs_fn:
            retriever_chain = self._build_retriever_chain(
                retriever, format_docs_fn
            ).with_config(run_name="FindDocs")
            formatted_chain = retriever_chain | RunnableLambda(format_docs_fn)
            context_map = RunnableMap(
                {
                    "context": formatted_chain,
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
        retriever: Runnable,
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
