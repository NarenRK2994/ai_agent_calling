"""Unit tests for workflow runner resolution helpers."""

from __future__ import annotations

import types
import unittest

from backend.workflow_runner import invoke_workflow_runner


class WorkflowRunnerTests(unittest.TestCase):
    """Verifies workflow runner invocation across supported signatures."""

    def test_invoke_workflow_runner_with_keyword_signature(self) -> None:
        seen = {}

        def runner(*, question, runtime, context):  # type: ignore[no-untyped-def]
            seen["question"] = question
            seen["runtime"] = runtime
            seen["context"] = context
            return "ok"

        result = invoke_workflow_runner(
            runner,
            question="Show unpaid invoices",
            runtime={"trace": True},
            context=types.SimpleNamespace(name="ctx"),
        )

        self.assertEqual("ok", result)
        self.assertEqual("Show unpaid invoices", seen["question"])

    def test_invoke_workflow_runner_with_positional_signature(self) -> None:
        seen = {}

        def runner(question, runtime, context):  # type: ignore[no-untyped-def]
            seen["question"] = question
            seen["runtime"] = runtime
            seen["context"] = context
            return "ok"

        result = invoke_workflow_runner(
            runner,
            question="Show unpaid invoices",
            runtime={"trace": True},
            context=types.SimpleNamespace(name="ctx"),
        )

        self.assertEqual("ok", result)
        self.assertEqual("Show unpaid invoices", seen["question"])


if __name__ == "__main__":
    unittest.main()
