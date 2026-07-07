"""SQL validation node implementation."""

from __future__ import annotations

from agents.base import BaseAgent
from agents.sql_validation import SQLValidator
from graph.state import ERPAgentState


class ValidationAgent(BaseAgent):
    """Validates generated Oracle SQL before execution."""

    def __init__(self, name: str, validator: SQLValidator | None = None) -> None:
        super().__init__(name)
        self.validator = validator or SQLValidator()

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Validate generated SQL and record any user-facing errors."""
        if not state.generated_sql:
            state.errors.append("SQL validation could not run because no SQL was generated.")
            return state

        result = self.validator.validate(state.generated_sql, state.relevant_metadata)
        if result.is_valid and result.normalized_sql:
            state.validated_sql = result.normalized_sql
            return state

        state.errors.extend(result.errors)
        return state
