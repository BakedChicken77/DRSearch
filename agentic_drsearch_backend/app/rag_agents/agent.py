"""
Defines the OpenAI Agent configured with our retrieval tool.
"""

from agents import Agent, ModelSettings, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from .tools import search_documents
from ..config import get_settings
from openai import AsyncAzureOpenAI

set_tracing_disabled(True)

settings = get_settings()

_SYSTEM_INSTRUCTIONS = """\
You are a research assistant.
Your knowledge comes ONLY from the company's private document store, \
accessed through the `search_documents` tool.

— When the user asks a factual question, first think whether you need to \
call `search_documents`. If so, call it with relevant keywords.
— The tool returns documents wrapped in <doc> tags; cite them by their \
numeric id in square brackets, e.g. [0].
— If no retrieved document answers the question, respond: \
"I'm not sure based on the provided documents."
— NEVER fabricate citations or reference documents you have not retrieved.
"""

openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version= settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    azure_deployment=settings.AZURE_OPENAI_LLM_DEPLOYMENT
)

agent = Agent(
    name="PG Vector RAG Agent",
    instructions=_SYSTEM_INSTRUCTIONS,
    model=OpenAIChatCompletionsModel(settings.AZURE_OPENAI_LLM_DEPLOYMENT,openai_client=openai_client),
    model_settings=ModelSettings(
        temperature=settings.AGENT_TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
    ),
    tools=[search_documents],
)

# Convenience wrapper for the routes
async def run_agent(question: str) -> str:
    """Run the agent against a single user question and return final answer."""
    result = await Runner.run(agent, question)
    return result.final_output
