"""Dataclasses representing ERP metadata documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ERPColumnMetadata:
    """Represents a single column inside an Oracle ERP table definition."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ERPRelationshipMetadata:
    """Describes how one ERP table joins to another table."""

    table: str
    join: str


@dataclass(frozen=True, slots=True)
class ERPTableMetadata:
    """Full metadata document for one ERP table."""

    module: str
    table: str
    description: str
    primary_key: str
    columns: tuple[ERPColumnMetadata, ...] = field(default_factory=tuple)
    relationships: tuple[ERPRelationshipMetadata, ...] = field(default_factory=tuple)
    business_questions: tuple[str, ...] = field(default_factory=tuple)
    source_path: Path | None = None

    @property
    def document_id(self) -> str:
        """Return a stable vector-store identifier for this metadata document."""
        return f"{self.module}::{self.table}"

    def to_document_text(self) -> str:
        """Flatten the metadata into a rich text payload for embedding."""
        column_lines = [f"{column.name}: {column.description}" for column in self.columns]
        relationship_lines = [
            f"{relationship.table} via {relationship.join}"
            for relationship in self.relationships
        ]
        sections = [
            f"Module: {self.module}",
            f"Table: {self.table}",
            f"Description: {self.description}",
            f"Primary Key: {self.primary_key}",
            "Columns:",
            *column_lines,
            "Relationships:",
            *relationship_lines,
            "Business Questions:",
            *self.business_questions,
        ]
        return "\n".join(sections)

    def to_vector_metadata(self) -> dict[str, object]:
        """Convert the table metadata into Chroma-compatible filter metadata."""
        return {
            "module": self.module,
            "table": self.table,
            "primary_key": self.primary_key,
            "source_path": str(self.source_path) if self.source_path else "",
        }
