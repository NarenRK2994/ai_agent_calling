"""Shared abstractions for graph-driven agent nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from graph.state import ERPAgentState


class BaseAgent(ABC):
    """Base contract for all workflow agents."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def run(self, state: ERPAgentState) -> ERPAgentState:
        """Execute the agent against the current workflow state."""

    def metadata(self) -> dict[str, Any]:
        """Return lightweight runtime metadata for diagnostics."""
        return {"name": self.name, "agent_type": self.__class__.__name__}
