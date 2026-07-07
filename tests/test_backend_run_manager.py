"""Unit tests for backend run session helpers."""

from __future__ import annotations

import unittest

from backend.run_manager import RunSession


class BackendRunManagerTests(unittest.TestCase):
    """Verifies backend snapshot serialization for frontend consumers."""

    def test_snapshot_payload_includes_progress_ratio(self) -> None:
        run = RunSession(run_id="run-1", question="Show unpaid invoices")
        run.controller.snapshot.timeline = [
            {"node_name": "Intent Detection", "execution_time_seconds": 0.2},
            {"node_name": "Schema Retrieval", "execution_time_seconds": 0.1},
        ]

        payload = run.snapshot_payload()

        self.assertIn("progress_ratio", payload)
        self.assertGreater(payload["progress_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
