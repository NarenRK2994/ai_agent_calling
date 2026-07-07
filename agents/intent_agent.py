"""Intent detection node implementation."""

from __future__ import annotations

from agents.base import BaseAgent
from graph.state import ERPAgentState
from llm.base import BaseLLM
from utils.prompt_loader import PromptTemplateLoader


class IntentAgent(BaseAgent):
    """Determines the business intent of a user question."""

    def __init__(
        self,
        name: str,
        llm: BaseLLM | None = None,
        prompt_loader: PromptTemplateLoader | None = None,
        *,
        template_name: str = "intent.txt",
    ) -> None:
        super().__init__(name)
        self.llm = llm
        self.prompt_loader = prompt_loader
        self.template_name = template_name

    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Classify the user question into a concise ERP analytics intent."""
        if self.llm is not None and self.prompt_loader is not None:
            template = self.prompt_loader.load(self.template_name)
            state.detected_intent = self.llm.generate_from_template(
                template,
                user_question=state.user_question,
            ).strip()
            return state

        state.detected_intent = self._heuristic_intent(state.user_question)
        return state

    def _heuristic_intent(self, question: str) -> str:
        """Fallback intent classification when no LLM is wired yet."""
        lowered = question.casefold()
        if any(keyword in lowered for keyword in ("count", "total", "sum", "average")):
            return "aggregation"
        if any(keyword in lowered for keyword in ("between", "after", "before", "date", "month", "year")):
            return "time_filtered_query"
        if any(keyword in lowered for keyword in ("list", "show", "display", "find")):
            return "lookup_query"
        return "general_erp_query"
