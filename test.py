"""Console-only workflow runner for manually testing one ERP AI Agent question."""

from __future__ import annotations

import os
import sys
from typing import Any

from backend.application import create_application_context
from backend.run_manager import DEFAULT_WORKFLOW_RUNNER
from backend.workflow_runner import invoke_workflow_runner, resolve_workflow_runner
from retriever.schema_loader import SchemaLoader


def _force_console_debug(runtime: Any) -> None:
    """Enable verbose console tracing for this ad-hoc test runner."""
    options = runtime.observability.options
    options.debug = True
    options.trace_sql = True
    options.trace_prompts = True
    options.trace_state = True
    options.trace_timing = True


def _read_question() -> str:
    """Read the test question from argv or interactive input."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    return input("Enter your ERP question: ").strip()


def main() -> int:
    """Run one workflow question and print all flow/errors to the console."""
    question = _read_question()
    if not question:
        print("Error: question is required.")
        return 1

    runner_path = os.getenv("ERP_AGENT_WORKFLOW_RUNNER", DEFAULT_WORKFLOW_RUNNER)

    context = create_application_context()
    _force_console_debug(context.runtime)

    schema_loader = SchemaLoader()
    loaded_tables = schema_loader.load(context.config.metadata_dir)

    print("\nCONFIGURATION")
    print(f"Metadata directory: {context.config.metadata_dir}")
    print(f"Loaded metadata tables: {len(loaded_tables)}")
    if loaded_tables:
        for table in loaded_tables:
            print(f"- {table.table} ({table.module})")
    else:
        print("- No metadata JSON files found. Add ERP table JSON files under the metadata directory.")

    try:
        runner = resolve_workflow_runner(runner_path)
        result = invoke_workflow_runner(
            runner,
            question=question,
            runtime=context.runtime,
            context=context,
        )
    except Exception as exc:
        print("\nERROR DURING WORKFLOW EXECUTION")
        print(str(exc))
        return 1

    trace_store = context.runtime.observability.trace_store
    traces = trace_store.list_traces()
    latest_trace = traces[-1] if traces else None

    if latest_trace:
        retrieved_tables = latest_trace.retrieved_tables or []
        similarity_scores = latest_trace.similarity_scores or []
        print("\nRETRIEVAL RESULTS")
        if retrieved_tables:
            for index, table_name in enumerate(retrieved_tables):
                score = similarity_scores[index] if index < len(similarity_scores) else None
                if score is None:
                    print(f"- {table_name}")
                else:
                    print(f"- {table_name} | score={score:.4f}")
        else:
            print("- No tables were retrieved for this question.")

    if latest_trace and latest_trace.errors:
        print("\nTRACE ERRORS")
        for error in latest_trace.errors:
            print(f"- {error}")
        return 1

    final_answer = getattr(result, "final_response", None) or getattr(result, "summary", None)
    if final_answer:
        print("\nFINAL ANSWER")
        print(final_answer)

    print(f"\nRunner used: {runner_path}")
    print("\nWorkflow completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
