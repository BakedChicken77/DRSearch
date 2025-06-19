from __future__ import annotations

import os
from typing import Dict, Tuple

from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import (
    OpenAIToolsAgentOutputParser,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import tool
from langchain_core.utils.function_calling import format_tool_to_openai_tool
from langchain_openai import AzureChatOpenAI

from app import System_Prompts
from app.chain.formatter import DocumentFormatter
from app.chain.history import HistorySerializer
from app.chain.mapping import PartNumberMapping
from app.chain.retriever import RetrieverFactory
from app.core.chain_config import _DEFAULT_INDEX, _NUMBER_OF_DOCS_RETRIEVED, RAG_ON
from app.index_config import INDEX_CONFIG

_agent_cache: Dict[Tuple[str, int], Runnable] = {}


def _agent_for(index_name: str, num_docs: int) -> Runnable:
    key = (index_name, num_docs)
    if key not in _agent_cache:
        from app.core import chain_config

        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
        cfg = INDEX_CONFIG.get(index_name)
        if cfg is None:
            system_prompt = System_Prompts.RESPONSE_TEMPLATE_CHATBOT
            mapping_name = None
        else:
            system_prompt = cfg["response_template"]
            mapping_name = cfg.get("PN_TO_FILE_MAPPING")

        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            temperature=0.0,
            model=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
            streaming=True,
        )

        tools = []
        if RAG_ON and cfg is not None:
            retriever = RetrieverFactory.build(index_name)
            formatter = DocumentFormatter(PartNumberMapping(mapping_name))

            @tool
            def search_docs(query: str) -> str:
                """Search relevant documents"""
                docs = retriever.get_relevant_documents(query)
                return formatter(docs)

            tools.append(search_docs)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        llm_with_tools = llm.bind(tools=[format_tool_to_openai_tool(t) for t in tools])

        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    x.get("intermediate_steps", [])
                ),
                "chat_history": lambda x: x["chat_history"],
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )

        executor = AgentExecutor(agent=agent, tools=tools)
        history = HistorySerializer()
        runnable = (
            RunnableLambda(
                lambda d: {
                    "input": d["question"],
                    "chat_history": history(d),
                }
            )
            | executor
        )
        _agent_cache[key] = runnable
    return _agent_cache[key]


def get_agent_executor(
    index_name: str | None = None, num_docs: int = _NUMBER_OF_DOCS_RETRIEVED
) -> Runnable:
    return _agent_for(index_name or _DEFAULT_INDEX, num_docs)


agent_chain: Runnable = RunnableLambda(
    lambda inputs: get_agent_executor(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
