"""SQL generation node implementation."""

from __future__ import annotations

import re

from agents.base import BaseAgent
from agents.sql_generation import SchemaPromptFormatter
from graph.state import ERPAgentState
from llm.base import BaseLLM
from utils.prompt_loader import PromptTemplateLoader


class SQLAgent(BaseAgent):
    """Generates Oracle SQL from the user question and retrieved schema."""

    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        prompt_loader: PromptTemplateLoader,
        *,
        template_name: str = "sql.txt",
        schema_formatter: SchemaPromptFormatter | None = None,
    ) -> None:
        super().__init__(name)
        self.llm = llm
        self.prompt_loader = prompt_loader
        self.template_name = template_name
        self.schema_formatter = schema_formatter or SchemaPromptFormatter()

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Build the SQL prompt from retrieved schema and generate Oracle SQL."""
        if state.prompt_text is not None:
            raw_output = self.llm.generate(state.prompt_text)
        else:
            template = self.prompt_loader.load(self.template_name)
            schema_context = self.schema_formatter.format(state.relevant_metadata)
            raw_output = self.llm.generate_from_template(
                template,
                user_question=state.user_question,
                schema_context=schema_context,
                validation_feedback="None",
            )
        state.generated_sql = self._extract_sql(raw_output)
        return state

    def _extract_sql(self, text: str) -> str:
        """Normalize the model output so downstream validation receives SQL only."""
        fenced_match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()
        return text.strip()
