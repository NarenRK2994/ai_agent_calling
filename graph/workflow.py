"""LangGraph workflow assembly for the ERP AI Agent."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agents.base import BaseAgent
from graph.state import ERPAgentState
from utils.exceptions import RateLimitError
from utils.observability import (
    build_node_details,
    build_node_warnings,
    trace_node,
)
from utils.runtime import RuntimeServices


def _run_agent(agent: BaseAgent, state: ERPAgentState, runtime: RuntimeServices, metric_name: str) -> ERPAgentState:
    """Execute one agent while collecting timing and execution logs."""
    with runtime.metrics.time_block(metric_name):
        runtime.execution_logs.record(agent.name, "started")
        updated_state = agent.run(state)
        runtime.execution_logs.record(
            agent.name,
            "completed" if not updated_state.errors else "completed_with_errors",
            errors=list(updated_state.errors),
        )
        return updated_state


def build_workflow(
    *,
    intent_agent: BaseAgent,
    schema_agent: BaseAgent,
    prompt_builder_agent: BaseAgent,
    sql_agent: BaseAgent,
    validation_agent: BaseAgent,
    execution_agent: BaseAgent,
    summary_agent: BaseAgent,
    runtime: RuntimeServices,
    max_validation_retries: int,
) -> Any:
    """Build and return the ERP AI Agent workflow graph."""
    from langgraph.graph import END, START, StateGraph

    @trace_node(
        "Intent Detection",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Intent Detection",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Intent Detection",
        ),
    )
    def intent_node(state: ERPAgentState) -> ERPAgentState:
        _enforce_rate_limit(runtime, state.session_id)
        runtime.conversation_memory.append(state.session_id, "user", state.user_question)
        return _run_agent(intent_agent, state, runtime, "intent_agent_seconds")

    @trace_node(
        "Schema Retrieval",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Schema Retrieval",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Schema Retrieval",
        ),
    )
    def retriever_node(state: ERPAgentState) -> ERPAgentState:
        cache_key = f"retrieval::{state.user_question.casefold()}"
        cached = runtime.cache.get(cache_key)
        if isinstance(cached, list):
            state.retrieval_results = cached
            state.relevant_metadata = cached
            state.relevant_tables = [item["table"] for item in cached]
            state.warnings.append("Schema retrieval was served from cache.")
            return state
        updated_state = _run_agent(schema_agent, state, runtime, "schema_agent_seconds")
        runtime.cache.set(cache_key, updated_state.retrieval_results)
        return updated_state

    @trace_node(
        "Prompt Builder",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Prompt Builder",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Prompt Builder",
        ),
    )
    def prompt_builder_node(state: ERPAgentState) -> ERPAgentState:
        return _run_agent(prompt_builder_agent, state, runtime, "prompt_builder_seconds")

    @trace_node(
        "Qwen Generation",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Qwen Generation",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Qwen Generation",
        ),
    )
    def sql_generator_node(state: ERPAgentState) -> ERPAgentState:
        updated_state = _run_agent(sql_agent, state, runtime, "sql_generator_seconds")
        if updated_state.generated_sql:
            runtime.sql_history.record(updated_state.user_question, updated_state.generated_sql, "generated")
            updated_state.sql_history.append(
                {"status": "generated", "sql": updated_state.generated_sql}
            )
        return updated_state

    @trace_node(
        "SQL Validation",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "SQL Validation",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "SQL Validation",
        ),
    )
    def validator_node(state: ERPAgentState) -> ERPAgentState:
        state.validation_attempts += 1
        errors_before = len(state.errors)
        updated_state = _run_agent(validation_agent, state, runtime, "validator_seconds")
        if len(updated_state.errors) > errors_before:
            runtime.sql_history.record(
                updated_state.user_question,
                updated_state.generated_sql or "",
                "validation_failed",
            )
            updated_state.retry_requested = updated_state.validation_attempts <= max_validation_retries
            if updated_state.retry_requested:
                updated_state.warnings.append("Validation failed; retry path enabled.")
        else:
            updated_state.retry_requested = False
        return updated_state

    @trace_node(
        "Oracle Execution",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Oracle Execution",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Oracle Execution",
        ),
    )
    def execution_node(state: ERPAgentState) -> ERPAgentState:
        updated_state = _run_agent(execution_agent, state, runtime, "execution_seconds")
        if updated_state.validated_sql:
            runtime.sql_history.record(
                updated_state.user_question,
                updated_state.validated_sql,
                "executed",
            )
        return updated_state

    @trace_node(
        "Summary Generation",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Summary Generation",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Summary Generation",
        ),
    )
    def summary_node(state: ERPAgentState) -> ERPAgentState:
        updated_state = _run_agent(summary_agent, state, runtime, "summary_seconds")
        if updated_state.summary:
            runtime.conversation_memory.append(state.session_id, "assistant", updated_state.summary)
        return updated_state

    @trace_node(
        "Final Response",
        observability=runtime.observability,
        details_builder=lambda _before, after: build_node_details(
            "Final Response",
            after,
            runtime.observability.options,
        ),
        warning_builder=lambda before, after: build_node_warnings(
            before,
            after,
            "Final Response",
        ),
    )
    def final_response_node(state: ERPAgentState) -> ERPAgentState:
        if state.errors and not state.validated_sql:
            state.final_response = "Request failed validation: " + " | ".join(state.errors)
        else:
            state.final_response = state.summary or "Request completed."
        runtime.metrics.increment("workflow_requests_total")
        runtime.execution_logs.record(
            "final_response",
            "completed",
            final_response=state.final_response,
            state=asdict(state),
        )
        return state

    graph = StateGraph(ERPAgentState)
    graph.add_node("intent", intent_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("prompt_builder", prompt_builder_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("validator", validator_node)
    graph.add_node("executor", execution_node)
    graph.add_node("summarizer", summary_node)
    graph.add_node("final_response", final_response_node)

    graph.add_edge(START, "intent")
    graph.add_edge("intent", "retriever")
    graph.add_edge("retriever", "prompt_builder")
    graph.add_edge("prompt_builder", "sql_generator")
    graph.add_edge("sql_generator", "validator")
    graph.add_conditional_edges(
        "validator",
        _next_after_validation,
        {
            "retry": "prompt_builder",
            "execute": "executor",
            "finish": "final_response",
        },
    )
    graph.add_edge("executor", "summarizer")
    graph.add_edge("summarizer", "final_response")
    graph.add_edge("final_response", END)
    return graph.compile()


def execute_workflow(compiled_graph: Any, initial_state: ERPAgentState, runtime: RuntimeServices) -> ERPAgentState:
    """Run the compiled LangGraph workflow with optional streamed debug output."""
    with runtime.observability.workflow_trace(initial_state.user_question):
        if runtime.observability.options.debug or runtime.observability.has_listeners:
            final_state = initial_state
            for event in compiled_graph.stream(initial_state):
                runtime.observability.record_raw_event(event)
                for node_name, node_state in event.items():
                    runtime.observability.update_from_state(node_state)
                    runtime.observability.print_stream_state(node_name, node_state)
                    final_state = node_state
            runtime.observability.print_final_trace()
            return final_state
        final_state = compiled_graph.invoke(initial_state)
        runtime.observability.update_from_state(final_state)
        runtime.observability.print_final_trace()
        return final_state


def _next_after_validation(state: ERPAgentState) -> str:
    """Route validation failures back into prompt building when retry is allowed."""
    if state.validated_sql:
        return "execute"
    if state.retry_requested:
        return "retry"
    return "finish"


def _enforce_rate_limit(runtime: RuntimeServices, session_id: str) -> None:
    """Enforce per-session request rate limits before the workflow starts."""
    decision = runtime.rate_limiter.allow(session_id)
    if not decision.allowed:
        raise RateLimitError(
            f"Rate limit exceeded. Retry after {decision.retry_after_seconds} second(s)."
        )
