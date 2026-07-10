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
            column_lines = self._extract_column_lines(item)
            section = "\n".join(
                [
                    f"Table: {item['table']}",
                    f"Module: {item['module']}",
                    f"Description: {item.get('description') or self._extract_table_description(item)}",
                    f"Primary Key: {item.get('primary_key', '')}",
                    "Columns:",
                    *column_lines,
                    "Relationships:",
                    *relationship_lines,
                ]
            )
            sections.append(section)
        return "\n\n".join(sections)

    def _extract_column_lines(self, item: dict[str, Any]) -> list[str]:
        """Prefer rich column descriptions from the retrieved document when available."""
        document = str(item.get("document", ""))
        extracted_lines = self._extract_document_section(document, "Columns:", "Relationships:")
        if extracted_lines:
            return [f"- {line}" for line in extracted_lines]
        return [f"- {column}" for column in item.get("columns", [])]

    def _extract_table_description(self, item: dict[str, Any]) -> str:
        """Read the table description from the retrieved document text."""
        document = str(item.get("document", ""))
        for line in document.splitlines():
            if line.startswith("Description:"):
                return line.removeprefix("Description:").strip()
        return ""

    def _extract_document_section(self, document: str, start_marker: str, end_marker: str) -> list[str]:
        """Extract raw lines between two headings in the embedded metadata document."""
        if not document:
            return []
        lines = [line.strip() for line in document.splitlines()]
        collecting = False
        section_lines: list[str] = []
        for line in lines:
            if line == start_marker:
                collecting = True
                continue
            if collecting and line == end_marker:
                break
            if collecting and line:
                section_lines.append(line)
        return section_lines
