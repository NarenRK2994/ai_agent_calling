"""Backend-side state management for dashboard workflow visualizations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DashboardSnapshot:
    """Mutable dashboard view model built from backend observability events."""

    question: str = ""
    trace_id: str | None = None
    current_node: str = "Idle"
    execution_status: str = "idle"
    retrieved_tables: list[str] = field(default_factory=list)
    similarity_scores: list[float] = field(default_factory=list)
    prompt: str | None = None
    generated_sql: str | None = None
    validation_result: str | None = None
    oracle_execution_time: float | None = None
    returned_rows: int = 0
    final_answer: str | None = None
    total_execution_time: float = 0.0
    timeline: list[dict[str, Any]] = field(default_factory=list)
    state_object: dict[str, Any] = field(default_factory=dict)
    trace_object: dict[str, Any] = field(default_factory=dict)
    raw_langgraph_events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def progress_ratio(self) -> float:
        """Return a normalized workflow progress value for progress bars."""
        total_nodes = 8
        return min(1.0, len(self.timeline) / total_nodes)


class DashboardController:
    """Consumes observability events and keeps the backend dashboard snapshot current."""

    def __init__(self) -> None:
        self.snapshot = DashboardSnapshot()

    def reset(self, question: str) -> None:
        """Reset dashboard state for a new workflow run."""
        self.snapshot = DashboardSnapshot(question=question, execution_status="queued")

    def handle_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Apply one observability event to the dashboard snapshot."""
        if event_type == "workflow_started":
            trace = payload.get("trace", {})
            self.snapshot.trace_id = trace.get("trace_id")
            self.snapshot.execution_status = "running"
            self.snapshot.trace_object = trace
            return

        if event_type == "trace_updated":
            trace = payload.get("trace", {})
            state = payload.get("state", {})
            self.snapshot.trace_object = trace
            self.snapshot.state_object = state
            self.snapshot.retrieved_tables = list(trace.get("retrieved_tables", []))
            self.snapshot.similarity_scores = list(trace.get("similarity_scores", []))
            self.snapshot.prompt = trace.get("prompt")
            self.snapshot.generated_sql = trace.get("generated_sql")
            self.snapshot.validation_result = trace.get("validation_result")
            self.snapshot.returned_rows = int(trace.get("rows_returned", 0))
            self.snapshot.final_answer = trace.get("final_answer")
            self.snapshot.total_execution_time = float(trace.get("execution_time", 0.0))
            self.snapshot.errors = list(trace.get("errors", []))
            self.snapshot.warnings = list(trace.get("warnings", []))
            self.snapshot.timeline = list(trace.get("timeline", []))
            self.snapshot.current_node = self.snapshot.timeline[-1]["node_name"] if self.snapshot.timeline else self.snapshot.current_node
            return

        if event_type == "node_trace":
            node_trace = payload.get("node_trace", {})
            self.snapshot.current_node = node_trace.get("node_name", self.snapshot.current_node)
            self.snapshot.timeline.append(
                {
                    "node_name": node_trace.get("node_name"),
                    "execution_time_seconds": node_trace.get("execution_time_seconds", 0.0),
                }
            )
            if node_trace.get("node_name") == "Oracle Execution":
                self.snapshot.oracle_execution_time = float(
                    node_trace.get("execution_time_seconds", 0.0)
                )
            self.snapshot.errors = list(node_trace.get("errors", []))
            self.snapshot.warnings = list(node_trace.get("warnings", []))
            return

        if event_type == "stream_state":
            self.snapshot.execution_status = "running"
            self.snapshot.current_node = payload.get("node_name", self.snapshot.current_node)
            self.snapshot.state_object = dict(payload.get("state", {}))
            return

        if event_type == "raw_event":
            self.snapshot.raw_langgraph_events.append(dict(payload.get("event", {})))
            return

        if event_type == "final_trace":
            trace = payload.get("trace", {})
            self.snapshot.trace_object = trace
            self.snapshot.execution_status = "completed" if not trace.get("errors") else "completed_with_errors"
            self.snapshot.total_execution_time = float(trace.get("execution_time", 0.0))
            self.snapshot.final_answer = trace.get("final_answer")
            return

        if event_type == "workflow_completed":
            trace = payload.get("trace", {})
            self.snapshot.trace_object = trace
            self.snapshot.execution_status = "completed" if not trace.get("errors") else "completed_with_errors"
