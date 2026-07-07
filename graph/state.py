"""Workflow state definitions for the ERP AI Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ERPAgentState:
    """Mutable workflow state passed between graph nodes."""

    user_question: str
    session_id: str = "default"
    detected_intent: str | None = None
    relevant_tables: list[str] = field(default_factory=list)
    relevant_metadata: list[dict[str, Any]] = field(default_factory=list)
    retrieval_results: list[dict[str, Any]] = field(default_factory=list)
    prompt_text: str | None = None
    prompt_version: str | None = None
    generated_sql: str | None = None
    validated_sql: str | None = None
    query_result: list[dict[str, Any]] = field(default_factory=list)
    sql_history: list[dict[str, str]] = field(default_factory=list)
    summary: str | None = None
    final_response: str | None = None
    validation_attempts: int = 0
    retry_requested: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
