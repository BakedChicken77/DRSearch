import os
from typing import List, Dict, Any, TypedDict
from datetime import datetime
from langgraph import StateGraph, END
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from .vector_store import VectorStoreService
from ..config import get_settings

settings = get_settings()

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    context: List[Dict[str, Any]]
    query: str
    response: str

class RAGAgent:
    """LangGraph based RAG agent."""

    def __init__(self) -> None:
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            deployment_name=settings.AZURE_OPENAI_DEPLOYMENT,
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15"),
            temperature=0.7,
        )
        self.store = VectorStoreService()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        def retrieve(state: AgentState) -> AgentState:
            state["context"] = self.store.search(state["query"], k=5)
            return state

        def generate(state: AgentState) -> AgentState:
            context_text = "\n".join(
                f"{c['metadata'].get('filename','')}: {c['content']}" for c in state["context"]
            )
            messages = [
                SystemMessage(content=f"Use context to answer.\n{context_text}")
            ]
            for m in state["messages"][-5:]:
                if m["role"] == "user":
                    messages.append(HumanMessage(content=m["content"]))
                else:
                    messages.append(AIMessage(content=m["content"]))
            messages.append(HumanMessage(content=state["query"]))
            resp = self.llm(messages)
            state["response"] = resp.content
            return state

        g = StateGraph(AgentState)
        g.add_node("retrieve", retrieve)
        g.add_node("generate", generate)
        g.add_edge("retrieve", "generate")
        g.add_edge("generate", END)
        g.set_entry_point("retrieve")
        return g.compile()

    async def run(self, query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        state = AgentState(messages=history, context=[], query=query, response="")
        res = self.graph.invoke(state)
        return {"response": res["response"], "context": res["context"], "timestamp": datetime.utcnow().isoformat()}
