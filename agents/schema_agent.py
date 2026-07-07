"""Schema retrieval agent implementation."""

from __future__ import annotations

from agents.base import BaseAgent
from graph.state import ERPAgentState
from retriever.retriever import LangChainSchemaRetriever


class SchemaAgent(BaseAgent):
    """Uses a LangChain retriever to find the most relevant ERP tables."""

    def __init__(
        self,
        name: str,
        retriever: LangChainSchemaRetriever,
        *,
        top_k: int = 5,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(name)
        self.retriever = retriever
        self.top_k = top_k
        self.filters = filters

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Retrieve top relevant ERP schema entries for the user question."""
        results = self.retriever.retrieve_with_scores(
            state.user_question,
            top_k=self.top_k,
            filters=self.filters,
        )
        state.retrieval_results = results
        state.relevant_tables = [result["table"] for result in results]
        state.relevant_metadata = results
        return state
