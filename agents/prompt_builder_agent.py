"""Prompt builder node implementation."""

from __future__ import annotations

from agents.base import BaseAgent
from agents.sql_generation import SchemaPromptFormatter
from graph.state import ERPAgentState
from utils.prompt_loader import PromptTemplateLoader
from utils.prompt_versioning import PromptVersionManager


class PromptBuilderAgent(BaseAgent):
    """Builds the final SQL-generation prompt from schema and user intent."""

    def __init__(
        self,
        name: str,
        prompt_loader: PromptTemplateLoader,
        prompt_versions: PromptVersionManager,
        *,
        template_name: str = "sql.txt",
        schema_formatter: SchemaPromptFormatter | None = None,
    ) -> None:
        super().__init__(name)
        self.prompt_loader = prompt_loader
        self.prompt_versions = prompt_versions
        self.template_name = template_name
        self.schema_formatter = schema_formatter or SchemaPromptFormatter()

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Render the SQL prompt and record the prompt template version."""
        template = self.prompt_loader.load(self.template_name)
        schema_context = self.schema_formatter.format(state.relevant_metadata)
        validation_feedback = "\n".join(state.errors) if state.errors else "None"
        state.prompt_text = template.format(
            user_question=state.user_question,
            schema_context=schema_context,
            validation_feedback=validation_feedback,
        )
        state.prompt_version = self.prompt_versions.resolve(self.template_name).sha256
        return state
