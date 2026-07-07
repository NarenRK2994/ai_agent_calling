"""SQL execution node implementation."""

from __future__ import annotations

from agents.base import BaseAgent
from database.base import BaseDatabaseClient
from graph.state import ERPAgentState


class ExecutionAgent(BaseAgent):
    """Executes validated SQL against the Oracle database connector."""

    def __init__(self, name: str, database_client: BaseDatabaseClient) -> None:
        super().__init__(name)
        self.database_client = database_client

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Execute the validated SQL and store the result rows in state."""
        if not state.validated_sql:
            state.errors.append("Execution could not start because no validated SQL was available.")
            return state
        dataframe = self.database_client.execute_query(state.validated_sql)
        state.query_result = dataframe.to_dict(orient="records")
        return state
