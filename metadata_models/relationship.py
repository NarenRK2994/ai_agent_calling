"""Relationship metadata models for Oracle ERP schema extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class RelationshipMetadata:
    """Represents a detected relationship between two Oracle ERP tables."""

    relationship_type: str
    join_column: str
    referenced_table: str
    referenced_column: str
    constraint_name: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the relationship into a JSON-friendly mapping."""
        return asdict(self)
