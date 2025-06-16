"""
Defines the OpenAI Agent configured with our retrieval tool.
"""

from agents import Agent, ModelSettings, Runner
from .tools import search_documents
from ..config import get_settings

settings = get_settings()

_SYSTEM_INSTRUCTIONS = """\
You are DR-Search, an internal research assistant.
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

agent = Agent(
    name="drsearch_agentic_rag",
    instructions=_SYSTEM_INSTRUCTIONS,
    model=settings.OPENAI_MODEL,
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
