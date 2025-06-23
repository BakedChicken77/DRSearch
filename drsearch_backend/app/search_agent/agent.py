from __future__ import annotations

from agents import (
    Agent,
    ModelSettings,
    Runner,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)
from openai import AsyncAzureOpenAI
import os

from .tools import similarity_search, keyword_search, hybrid_search

set_tracing_disabled(True)

openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
)


_SYSTEM_INSTRUCTIONS = """
Your task is to answer the user's question using the following tools available to you:
1) similarity_search: Retrieve top 3 chunks of text most similar to the provided input query.

If there are any issues with using the tool, provide details of the errors.
"""

agent = Agent(
    name="RAG Search Agent",
    instructions=_SYSTEM_INSTRUCTIONS,
    model=OpenAIChatCompletionsModel(
        os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"), openai_client=openai_client
    ),
    model_settings=ModelSettings(temperature=0.0),
    tools=[similarity_search, keyword_search, hybrid_search],
)


async def run_agent(question: str, history: list[str] | None = None) -> str:
    result = await Runner.run(agent, question, context={"history": history or []})
    return result.final_output
