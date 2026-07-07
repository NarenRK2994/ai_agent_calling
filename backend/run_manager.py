"""Background run management for the React dashboard backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from backend.application import ApplicationContext
from backend.dashboard_state import DashboardController
from backend.workflow_runner import invoke_workflow_runner, resolve_workflow_runner

DEFAULT_WORKFLOW_RUNNER = "backend.runner:run_question"
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RunSession:
    """Represents one live or completed workflow run exposed by the backend."""

    run_id: str
    question: str
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    controller: DashboardController = field(default_factory=DashboardController)
    events: list[dict[str, Any]] = field(default_factory=list)
    queue: Queue[dict[str, Any]] = field(default_factory=Queue)
    error_message: str | None = None

    def snapshot_payload(self) -> dict[str, Any]:
        """Return the current dashboard snapshot as a serializable dictionary."""
        payload = asdict(self.controller.snapshot)
        payload["progress_ratio"] = self.controller.snapshot.progress_ratio
        return payload


class RunManager:
    """Starts workflow runs and relays observability events to API clients."""

    def __init__(self, context: ApplicationContext) -> None:
        self.context = context
        self._runs: dict[str, RunSession] = {}
        self._lock = Lock()

    def create_run(self, question: str) -> RunSession:
        """Create a background run and start streaming its events."""
        run = RunSession(run_id=str(uuid4()), question=question)
        run.controller.reset(question)
        with self._lock:
            self._runs[run.run_id] = run
        worker = Thread(target=self._execute_run, args=(run,), daemon=True)
        worker.start()
        return run

    def get_run(self, run_id: str) -> RunSession | None:
        """Return one run session by id."""
        return self._runs.get(run_id)

    def event_stream(self, run_id: str):
        """Yield server-sent events for a given run until completion."""
        run = self.get_run(run_id)
        if run is None:
            yield self._to_sse("error", {"message": "Run not found."})
            return

        for existing in run.events:
            yield self._to_sse(existing["event_type"], existing["payload"])

        while True:
            try:
                event = run.queue.get(timeout=0.5)
            except Empty:
                if run.status in {"completed", "failed"}:
                    break
                continue
            yield self._to_sse(event["event_type"], event["payload"])
            if event["event_type"] == "workflow_completed":
                break

    def _execute_run(self, run: RunSession) -> None:
        """Run the existing workflow logic and capture observability events."""
        listener = self._build_listener(run)
        runtime = self.context.runtime
        runtime.observability.subscribe(listener)
        try:
            run.status = "running"
            runner_path = os.getenv("ERP_AGENT_WORKFLOW_RUNNER", DEFAULT_WORKFLOW_RUNNER)
            runner = resolve_workflow_runner(runner_path)
            invoke_workflow_runner(
                runner,
                question=run.question,
                runtime=runtime,
                context=self.context,
            )
            run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            self._publish(
                run,
                "error",
                {"message": str(exc), "run_id": run.run_id},
            )
        finally:
            if not run.events or run.events[-1]["event_type"] != "workflow_completed":
                self._publish(
                    run,
                    "workflow_completed",
                    {
                        "run_id": run.run_id,
                        "status": run.status,
                        "snapshot": run.snapshot_payload(),
                    },
                )
            runtime.observability.unsubscribe(listener)

    def _build_listener(self, run: RunSession):
        """Create an observability listener bound to a single run session."""

        def listener(event_type: str, payload: dict[str, Any]) -> None:
            run.controller.handle_event(event_type, payload)
            self._log_event_to_console(run, event_type, payload)
            self._publish(
                run,
                event_type,
                {
                    "run_id": run.run_id,
                    "payload": payload,
                    "snapshot": run.snapshot_payload(),
                },
            )

        return listener

    def _log_event_to_console(self, run: RunSession, event_type: str, payload: dict[str, Any]) -> None:
        """Print workflow progress details to the Django console for each important node."""
        if event_type == "workflow_started":
            LOGGER.info("Workflow started | run_id=%s | question=%s", run.run_id, run.question)
            return

        if event_type == "node_trace":
            node_trace = payload.get("node_trace", {})
            node_name = node_trace.get("node_name", "Unknown Node")
            output_state = node_trace.get("output_state", {})
            LOGGER.info("Node completed | run_id=%s | node=%s", run.run_id, node_name)

            if node_name == "Intent Detection":
                LOGGER.info(
                    "Detected intent | run_id=%s | intent=%s",
                    run.run_id,
                    output_state.get("detected_intent", "N/A"),
                )
                return

            if node_name == "Schema Retrieval":
                retrieval_results = output_state.get("retrieval_results", [])
                if not retrieval_results:
                    LOGGER.warning("No tables retrieved | run_id=%s", run.run_id)
                    return
                for result in retrieval_results:
                    table_name = result.get("table", "UNKNOWN")
                    score = float(result.get("similarity_score", 0.0))
                    columns = ", ".join(result.get("columns", [])[:10]) or "No columns"
                    relationships = ", ".join(
                        f"{item.get('table')} via {item.get('join')}"
                        for item in result.get("relationships", [])[:5]
                    ) or "No relationships"
                    LOGGER.info(
                        "Retrieved table | run_id=%s | table=%s | score=%.4f | columns=%s | relationships=%s",
                        run.run_id,
                        table_name,
                        score,
                        columns,
                        relationships,
                    )
                return

            if node_name == "Qwen Generation":
                generated_sql = output_state.get("generated_sql", "")
                if generated_sql:
                    LOGGER.info("Generated SQL | run_id=%s\n%s", run.run_id, generated_sql)
                return

            if node_name == "SQL Validation":
                validated_sql = output_state.get("validated_sql")
                errors = output_state.get("errors", [])
                if validated_sql:
                    LOGGER.info("SQL validation passed | run_id=%s", run.run_id)
                elif errors:
                    LOGGER.error(
                        "SQL validation failed | run_id=%s | errors=%s",
                        run.run_id,
                        " | ".join(errors),
                    )
                return

            if node_name == "Oracle Execution":
                query_result = output_state.get("query_result", [])
                LOGGER.info(
                    "Oracle execution complete | run_id=%s | rows_returned=%s",
                    run.run_id,
                    len(query_result),
                )
                return

            if node_name == "Final Response":
                final_answer = output_state.get("final_response") or output_state.get("summary") or ""
                if final_answer:
                    LOGGER.info("Final answer | run_id=%s | answer=%s", run.run_id, final_answer)
                return

        if event_type == "workflow_completed":
            trace = payload.get("trace", {})
            LOGGER.info(
                "Workflow completed | run_id=%s | errors=%s | total_time=%.2f sec",
                run.run_id,
                len(trace.get("errors", [])),
                float(trace.get("execution_time", 0.0)),
            )

    def _publish(self, run: RunSession, event_type: str, payload: dict[str, Any]) -> None:
        """Store and enqueue one event for the frontend."""
        event = {"event_type": event_type, "payload": payload}
        run.events.append(event)
        run.queue.put(event)

    def _to_sse(self, event_type: str, payload: dict[str, Any]) -> str:
        """Encode one event as a server-sent event string."""
        return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"
