"""Unit tests for dashboard state management."""

from __future__ import annotations

import unittest

from backend.dashboard_state import DashboardController


class DashboardControllerTests(unittest.TestCase):
    """Verifies dashboard snapshot updates from observability events."""

    def test_controller_tracks_trace_updates_and_events(self) -> None:
        controller = DashboardController()
        controller.reset("Show unpaid invoices")

        controller.handle_event(
            "workflow_started",
            {"trace": {"trace_id": "trace-1", "question": "Show unpaid invoices"}},
        )
        controller.handle_event(
            "trace_updated",
            {
                "trace": {
                    "retrieved_tables": ["AP_INVOICES_ALL", "AP_SUPPLIERS"],
                    "similarity_scores": [0.96, 0.93],
                    "prompt": "Prompt text",
                    "generated_sql": "select * from ap_invoices_all",
                    "validation_result": "PASS",
                    "rows_returned": 12,
                    "final_answer": "Found 12 invoices.",
                    "timeline": [{"node_name": "Schema Retrieval", "execution_time_seconds": 0.12}],
                    "errors": [],
                    "warnings": [],
                    "execution_time": 0.5,
                },
                "state": {"detected_intent": "sql"},
            },
        )
        controller.handle_event(
            "raw_event",
            {"event": {"retriever": {"relevant_tables": ["AP_INVOICES_ALL"]}}},
        )

        snapshot = controller.snapshot
        self.assertEqual("trace-1", snapshot.trace_id)
        self.assertEqual(["AP_INVOICES_ALL", "AP_SUPPLIERS"], snapshot.retrieved_tables)
        self.assertEqual("PASS", snapshot.validation_result)
        self.assertEqual(1, len(snapshot.raw_langgraph_events))
        self.assertGreater(snapshot.progress_ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
