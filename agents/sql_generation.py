"""Support classes for safe SQL prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SQLGenerationInput:
    """Input payload used to build a SQL generation prompt."""

    user_question: str
    retrieved_schema: list[dict[str, Any]]


class SchemaPromptFormatter:
    """Formats retrieved ERP schema into a compact prompt-friendly text block."""

    def format(self, schema_items: list[dict[str, Any]]) -> str:
        """Render retrieved schema items into a deterministic prompt context."""
        sections: list[str] = []
        for item in schema_items:
            relationship_lines = [
                f"- {relationship['table']} via {relationship['join']}"
                for relationship in item.get("relationships", [])
            ]
            column_lines = [f"- {column}" for column in item.get("columns", [])]
            section = "\n".join(
                [
                    f"Table: {item['table']}",
                    f"Module: {item['module']}",
                    f"Primary Key: {item.get('primary_key', '')}",
                    "Columns:",
                    *column_lines,
                    "Relationships:",
                    *relationship_lines,
                ]
            )
            sections.append(section)
        return "\n\n".join(sections)
