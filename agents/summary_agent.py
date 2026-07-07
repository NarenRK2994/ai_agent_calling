"""Result summarization node implementation."""

from __future__ import annotations

import json

from agents.base import BaseAgent
from graph.state import ERPAgentState
from llm.base import BaseLLM
from utils.prompt_loader import PromptTemplateLoader


class SummaryAgent(BaseAgent):
    """Summarizes database query results for the user."""

    def __init__(
        self,
        name: str,
        llm: BaseLLM | None = None,
        prompt_loader: PromptTemplateLoader | None = None,
        *,
        template_name: str = "summary.txt",
    ) -> None:
        super().__init__(name)
        self.llm = llm
        self.prompt_loader = prompt_loader
        self.template_name = template_name

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Summarize the execution result using the local LLM or a deterministic fallback."""
        if self.llm is not None and self.prompt_loader is not None:
            template = self.prompt_loader.load(self.template_name)
            state.summary = self.llm.generate_from_template(
                template,
                user_question=state.user_question,
                query_result=json.dumps(state.query_result, default=str),
            ).strip()
            return state

        row_count = len(state.query_result)
        state.summary = f"Query returned {row_count} row(s)."
        return state
