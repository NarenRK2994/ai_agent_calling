"""Debug tracing, colored console output, and workflow observability helpers."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, ParamSpec, TypeVar
from uuid import uuid4

from config import RuntimeConfig

try:
    from rich.console import Console
    from rich.panel import Panel

    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    Console = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


P = ParamSpec("P")
R = TypeVar("R")


@dataclass(slots=True)
class TraceOptions:
    """Feature flags controlling debug and tracing output."""

    debug: bool
    trace_sql: bool
    trace_prompts: bool
    trace_state: bool
    trace_timing: bool

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "TraceOptions":
        """Build trace options from the runtime configuration."""
        return cls(
            debug=config.debug,
            trace_sql=config.trace_sql,
            trace_prompts=config.trace_prompts,
            trace_state=config.trace_state,
            trace_timing=config.trace_timing,
        )


@dataclass(slots=True)
class NodeTrace:
    """Detailed trace entry for one workflow node execution."""

    node_name: str
    start_time: str
    end_time: str
    execution_time_seconds: float
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TimelineEntry:
    """Represents one line in the execution timeline."""

    node_name: str
    execution_time_seconds: float


@dataclass(slots=True)
class AgentTrace:
    """Top-level trace object for one full agent run."""

    trace_id: str
    timestamp: str
    question: str
    intent: str | None = None
    retrieved_tables: list[str] = field(default_factory=list)
    similarity_scores: list[float] = field(default_factory=list)
    prompt: str | None = None
    generated_sql: str | None = None
    validation_result: str | None = None
    execution_time: float = 0.0
    rows_returned: int = 0
    final_answer: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_traces: list[NodeTrace] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    raw_langgraph_events: list[dict[str, Any]] = field(default_factory=list)


class TraceStore:
    """Stores traces in memory for later export to external backends."""

    def __init__(self) -> None:
        self._traces: list[AgentTrace] = []
        self._active_traces: dict[str, AgentTrace] = {}

    def start_trace(self, question: str) -> AgentTrace:
        """Create and register a new active trace."""
        trace = AgentTrace(
            trace_id=str(uuid4()),
            timestamp=_utc_now_iso(),
            question=question,
        )
        self._traces.append(trace)
        self._active_traces[trace.trace_id] = trace
        return trace

    def list_traces(self) -> list[AgentTrace]:
        """Return all stored traces."""
        return list(self._traces)

    def finalize(self, trace_id: str) -> None:
        """Mark a trace as finalized while keeping it in memory."""
        self._active_traces.pop(trace_id, None)


class DebugConsole:
    """Prints colored debug output for node and workflow execution."""

    def __init__(self, options: TraceOptions) -> None:
        self.options = options
        self._console = Console() if RICH_AVAILABLE and Console is not None else None
        self._node_counter = 0

    def print_node_trace(self, trace: NodeTrace) -> None:
        """Print one formatted node trace when debug mode is enabled."""
        if not self.options.debug:
            return
        self._node_counter += 1
        body = self._render_node_trace(trace)
        self._print_panel(
            title=f"NODE {self._node_counter} - {trace.node_name}",
            body=body,
            color="blue",
        )

    def print_stream_state(self, node_name: str, state_snapshot: dict[str, Any]) -> None:
        """Print the post-node state snapshot during streamed execution."""
        if not self.options.debug:
            return
        body = "Node Finished\n\n"
        body += f"Current Node: {node_name}\n\n"
        body += json.dumps(state_snapshot, indent=2, default=str)
        self._print_panel("STREAM UPDATE", body, "cyan")

    def print_final_trace(self, trace: AgentTrace) -> None:
        """Print the final trace summary and execution timeline."""
        if not self.options.debug:
            return
        timeline_lines = [
            f"{entry.node_name}: {entry.execution_time_seconds:.2f} sec"
            for entry in trace.timeline
        ]
        timeline_lines.append("-" * 25)
        timeline_lines.append(f"Total: {trace.execution_time:.2f} sec")
        sql_text = trace.generated_sql or "N/A"
        if not self.options.trace_sql:
            sql_text = "[hidden]"
        body = "\n".join(
            [
                f"Question: {trace.question}",
                f"SQL: {sql_text}",
                f"Rows: {trace.rows_returned}",
                f"Final Answer: {trace.final_answer or 'N/A'}",
                "",
                "Execution Timeline:",
                *timeline_lines,
            ]
        )
        self._print_panel("FINAL RESPONSE", body, "green" if not trace.errors else "red")

    def _render_node_trace(self, trace: NodeTrace) -> str:
        """Render the text body for one node trace."""
        lines = [
            f"Start Time: {trace.start_time}",
            f"End Time: {trace.end_time}",
            f"Execution Time: {trace.execution_time_seconds:.2f} sec",
        ]
        if self.options.trace_state:
            lines.extend(
                [
                    "",
                    "Input State:",
                    json.dumps(trace.input_state, indent=2, default=str),
                    "",
                    "Output State:",
                    json.dumps(trace.output_state, indent=2, default=str),
                ]
            )
        if trace.details:
            lines.extend(["", "Details:"])
            for key, value in trace.details.items():
                lines.append(f"{key}: {value}")
        if trace.errors:
            lines.extend(["", "Errors:"] + trace.errors)
        if trace.warnings:
            lines.extend(["", "Warnings:"] + trace.warnings)
        return "\n".join(lines)

    def _print_panel(self, title: str, body: str, color: str) -> None:
        """Print through Rich when available, otherwise fall back to plain text."""
        if self._console is not None and Panel is not None:
            self._console.print(Panel(body, title=title, border_style=color))
            return
        print(f"\n{'=' * 50}\n{title}\n{'=' * 50}\n{body}\n")


class ObservabilityManager:
    """Coordinates trace storage, per-node tracing, and debug output."""

    def __init__(
        self,
        options: TraceOptions,
        *,
        trace_store: TraceStore | None = None,
        debug_console: DebugConsole | None = None,
    ) -> None:
        self.options = options
        self.trace_store = trace_store or TraceStore()
        self.debug_console = debug_console or DebugConsole(options)
        self._trace_stack: list[AgentTrace] = []
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []

    @property
    def current_trace(self) -> AgentTrace | None:
        """Return the active trace for the current workflow run, if any."""
        return self._trace_stack[-1] if self._trace_stack else None

    @property
    def has_listeners(self) -> bool:
        """Return whether any external subscribers are listening for trace events."""
        return bool(self._listeners)

    def subscribe(self, listener: Callable[[str, dict[str, Any]], None]) -> None:
        """Register an external listener for observability events."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, dict[str, Any]], None]) -> None:
        """Remove a previously registered listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    @contextmanager
    def workflow_trace(self, question: str) -> Any:
        """Create a top-level trace context for one workflow run."""
        trace = self.trace_store.start_trace(question)
        self._trace_stack.append(trace)
        started_at = time.perf_counter()
        self._emit("workflow_started", {"trace": asdict(trace)})
        try:
            yield trace
        finally:
            trace.execution_time = time.perf_counter() - started_at
            self._emit("workflow_completed", {"trace": asdict(trace)})
            self.trace_store.finalize(trace.trace_id)
            self._trace_stack.pop()

    def record_node_trace(self, node_trace: NodeTrace) -> None:
        """Append a node trace to the active trace and print it when enabled."""
        trace = self.current_trace
        if trace is None:
            return
        trace.node_traces.append(node_trace)
        trace.timeline.append(
            TimelineEntry(
                node_name=node_trace.node_name,
                execution_time_seconds=node_trace.execution_time_seconds,
            )
        )
        self.debug_console.print_node_trace(node_trace)
        self._emit("node_trace", {"node_trace": asdict(node_trace)})

    def update_from_state(self, state: Any) -> None:
        """Project the latest workflow state into the active top-level trace."""
        trace = self.current_trace
        if trace is None:
            return
        snapshot = snapshot_state(state)
        trace.intent = snapshot.get("detected_intent")
        trace.retrieved_tables = list(snapshot.get("relevant_tables", []))
        trace.similarity_scores = [
            float(item.get("similarity_score", 0.0))
            for item in snapshot.get("retrieval_results", [])
            if isinstance(item, dict)
        ]
        trace.prompt = snapshot.get("prompt_text")
        trace.generated_sql = snapshot.get("generated_sql")
        trace.validation_result = (
            "PASS" if snapshot.get("validated_sql") else "FAIL" if snapshot.get("errors") else None
        )
        trace.rows_returned = len(snapshot.get("query_result", []))
        trace.final_answer = snapshot.get("final_response") or snapshot.get("summary")
        trace.errors = list(snapshot.get("errors", []))
        trace.warnings = list(snapshot.get("warnings", []))
        self._emit("trace_updated", {"trace": asdict(trace), "state": snapshot})

    def print_stream_state(self, node_name: str, state: Any) -> None:
        """Print the streamed state update for a completed node."""
        if self.options.debug:
            self.debug_console.print_stream_state(node_name, snapshot_state(state))
        self._emit(
            "stream_state",
            {"node_name": node_name, "state": snapshot_state(state)},
        )

    def print_final_trace(self) -> None:
        """Print the final response panel for the active trace."""
        trace = self.current_trace
        if trace is not None:
            self.debug_console.print_final_trace(trace)
            self._emit("final_trace", {"trace": asdict(trace)})

    def record_raw_event(self, event: dict[str, Any]) -> None:
        """Store one raw LangGraph event and notify subscribers."""
        trace = self.current_trace
        if trace is None:
            return
        serialized_event = snapshot_state(event)
        trace.raw_langgraph_events.append(serialized_event)
        self._emit("raw_event", {"event": serialized_event})

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Send an event payload to all registered listeners."""
        for listener in list(self._listeners):
            listener(event_type, payload)


def trace_node(
    node_name: str,
    *,
    observability: ObservabilityManager,
    details_builder: Callable[[Any, Any], dict[str, Any]] | None = None,
    warning_builder: Callable[[Any, Any], list[str]] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that automatically traces a workflow node."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            state_before = _extract_state_from_call(args, kwargs)
            input_snapshot = snapshot_state(state_before)
            started_at = time.perf_counter()
            start_label = _local_time_label()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                error_trace = NodeTrace(
                    node_name=node_name,
                    start_time=start_label,
                    end_time=_local_time_label(),
                    execution_time_seconds=time.perf_counter() - started_at,
                    input_state=input_snapshot,
                    output_state=input_snapshot,
                    errors=[str(exc)],
                )
                observability.record_node_trace(error_trace)
                raise
            output_snapshot = snapshot_state(result)
            node_trace = NodeTrace(
                node_name=node_name,
                start_time=start_label,
                end_time=_local_time_label(),
                execution_time_seconds=time.perf_counter() - started_at,
                input_state=input_snapshot,
                output_state=output_snapshot,
                errors=list(output_snapshot.get("errors", [])),
                warnings=warning_builder(state_before, result) if warning_builder else [],
                details=details_builder(state_before, result) if details_builder else {},
            )
            observability.update_from_state(result)
            observability.record_node_trace(node_trace)
            return result

        return wrapper

    return decorator


def snapshot_state(state: Any) -> dict[str, Any]:
    """Convert a workflow state object into a serializable dictionary snapshot."""
    if state is None:
        return {}
    if is_dataclass(state):
        return asdict(state)
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(vars(state))
    return {"value": state}


def build_node_details(node_name: str, output_state: Any, options: TraceOptions) -> dict[str, Any]:
    """Build human-readable debug details tailored to each workflow node."""
    snapshot = snapshot_state(output_state)
    details: dict[str, Any] = {}
    if node_name == "Intent Detection":
        details["Intent"] = snapshot.get("detected_intent", "N/A")
    elif node_name == "Schema Retrieval":
        details["Embedding Model"] = "BAAI/bge-large-en-v1.5"
        lines = []
        for item in snapshot.get("retrieval_results", []):
            if isinstance(item, dict):
                columns = ", ".join(item.get("columns", [])[:8]) or "No columns"
                relationships = ", ".join(
                    f"{relationship.get('table')} via {relationship.get('join')}"
                    for relationship in item.get("relationships", [])[:4]
                    if isinstance(relationship, dict)
                ) or "No relationships"
                lines.append(
                    f"{item.get('table')} ({item.get('similarity_score', 0.0):.2f}) | "
                    f"Columns: {columns} | Relationships: {relationships}"
                )
        details["Retrieved Tables"] = ", ".join(lines) if lines else "None"
    elif node_name == "Prompt Builder":
        prompt_text = snapshot.get("prompt_text") or ""
        details["Prompt Tokens"] = estimate_token_count(prompt_text)
        details["Prompt Characters"] = len(prompt_text)
        if options.trace_prompts:
            details["Prompt Preview"] = truncate_text(prompt_text, 800)
    elif node_name == "Qwen Generation":
        details["Generated SQL"] = snapshot.get("generated_sql", "") if options.trace_sql else "[hidden]"
    elif node_name == "SQL Validation":
        details["Validation Result"] = "PASS" if snapshot.get("validated_sql") else "FAIL"
    elif node_name == "Oracle Execution":
        details["Rows Returned"] = len(snapshot.get("query_result", []))
        if options.trace_sql:
            details["SQL"] = snapshot.get("validated_sql") or snapshot.get("generated_sql") or ""
    elif node_name == "Summary Generation":
        details["Answer"] = truncate_text(snapshot.get("summary") or "", 300)
    elif node_name == "Final Response":
        details["Rows"] = len(snapshot.get("query_result", []))
        details["Final Answer"] = truncate_text(snapshot.get("final_response") or "", 300)
    return details


def build_node_warnings(input_state: Any, output_state: Any, node_name: str) -> list[str]:
    """Create warning messages for notable but non-fatal conditions."""
    input_snapshot = snapshot_state(input_state)
    output_snapshot = snapshot_state(output_state)
    warnings: list[str] = []
    if node_name == "Schema Retrieval" and not output_snapshot.get("retrieval_results"):
        warnings.append("No schema results were retrieved.")
    if node_name == "SQL Validation" and output_snapshot.get("retry_requested"):
        warnings.append("Validation failed and the workflow requested a retry.")
    if node_name == "Oracle Execution" and not output_snapshot.get("query_result"):
        warnings.append("Query executed successfully but returned no rows.")
    if len(output_snapshot.get("errors", [])) > len(input_snapshot.get("errors", [])):
        warnings.append("New errors were added during this node.")
    return warnings


def truncate_text(text: str, limit: int) -> str:
    """Shorten long debug text while keeping it readable."""
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def estimate_token_count(text: str) -> int:
    """Estimate token count for debug display without requiring a tokenizer."""
    return len(text.split())


def _extract_state_from_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Find the workflow state argument from a traced function call."""
    if "state" in kwargs:
        return kwargs["state"]
    return args[0] if args else None


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _local_time_label() -> str:
    """Return the current local time label for console output."""
    return datetime.now().strftime("%H:%M:%S")
