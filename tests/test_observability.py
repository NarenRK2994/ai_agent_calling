"""Unit tests for observability and tracing helpers."""

from __future__ import annotations

import unittest

from graph.state import ERPAgentState
from utils.observability import (
    ObservabilityManager,
    TraceOptions,
    build_node_details,
    snapshot_state,
    trace_node,
)


class ObservabilityTests(unittest.TestCase):
    """Verifies trace capture, state snapshots, and node decorators."""

    def test_trace_node_records_execution(self) -> None:
        manager = ObservabilityManager(
            TraceOptions(
                debug=False,
                trace_sql=True,
                trace_prompts=True,
                trace_state=True,
                trace_timing=True,
            )
        )

        @trace_node(
            "Intent Detection",
            observability=manager,
            details_builder=lambda _before, after: build_node_details(
                "Intent Detection",
                after,
                manager.options,
            ),
        )
        def run_node(state: ERPAgentState) -> ERPAgentState:
            state.detected_intent = "sql"
            return state

        with manager.workflow_trace("Show unpaid invoices"):
            state = run_node(ERPAgentState(user_question="Show unpaid invoices"))
            manager.update_from_state(state)

        traces = manager.trace_store.list_traces()
        self.assertEqual(1, len(traces))
        self.assertEqual("sql", traces[0].intent)
        self.assertEqual(1, len(traces[0].node_traces))
        self.assertEqual("Intent Detection", traces[0].node_traces[0].node_name)

    def test_snapshot_state_serializes_dataclass(self) -> None:
        snapshot = snapshot_state(ERPAgentState(user_question="hello"))
        self.assertEqual("hello", snapshot["user_question"])
        self.assertIn("errors", snapshot)


if __name__ == "__main__":
    unittest.main()
