from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from langchain.schema.runnable import RunnableLambda
from openai import AsyncAzureOpenAI

try:
    from agents import (Agent, OpenAIChatCompletionsModel, Runner,
                        function_tool, set_default_openai_client)
    from agents.model_settings import ModelSettings

    OPENAI_AGENTS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency missing
    OPENAI_AGENTS_AVAILABLE = False

    # Dummy stand-ins so type checkers are satisfied
    def function_tool(func):
        return func


from app.chain.retriever import RetrieverFactory
from app.core import chain_config

logger = logging.getLogger(__name__)


def _init_openai_client() -> AsyncAzureOpenAI:
    client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    )
    if OPENAI_AGENTS_AVAILABLE:
        set_default_openai_client(client)
    return client


def build_agent_chain(index_name: str) -> RunnableLambda:
    """Return a Runnable that executes the RAG search agent."""
    client = _init_openai_client()
    retriever = RetrieverFactory.build(index_name)

    @function_tool
    async def similarity_search(
        query: str,
        k: int = chain_config._NUMBER_OF_DOCS_RETRIEVED,
    ) -> str:
        docs = await retriever.aget_relevant_documents(query)
        docs = docs[:k]
        return "\n\n".join(d.page_content for d in docs)

    if OPENAI_AGENTS_AVAILABLE:
        agent = Agent(
            name="DRSearch Agent",
            instructions="Answer questions by searching the document database.",
            tools=[similarity_search],
            model=OpenAIChatCompletionsModel(
                model=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
                openai_client=client,
            ),
            model_settings=ModelSettings(temperature=0.0),
        )

        async def _invoke_async(inputs: dict[str, Any]) -> str:
            result = await Runner.run(
                agent,
                inputs.get("question", ""),
                context={"history": inputs.get("chat_history", [])},
            )
            return result.final_output

        def _invoke(inputs: dict[str, Any]) -> str:
            return asyncio.run(_invoke_async(inputs))

    else:
        logger.warning("openai-agents not available, falling back to simple retrieval")

        async def _invoke_async(inputs: dict[str, Any]) -> str:
            return await similarity_search(inputs.get("question", ""))

        def _invoke(inputs: dict[str, Any]) -> str:
            return asyncio.run(_invoke_async(inputs))

    return RunnableLambda(_invoke)
