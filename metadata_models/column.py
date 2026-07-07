"""Column metadata models for Oracle ERP schema extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from metadata_models.business_rule import BusinessRuleMetadata


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    """Represents a single Oracle table column with technical and business attributes."""

    name: str
    description: str
    data_type: str
    nullable: bool
    data_length: int | None = None
    data_precision: int | None = None
    data_scale: int | None = None
    default_value: str | None = None
    category: str = "Other"
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_table: str | None = None
    referenced_column: str | None = None
    business_rules: tuple[BusinessRuleMetadata, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Serialize the column into a JSON-friendly mapping."""
        payload = asdict(self)
        payload["business_rules"] = [rule.to_dict() for rule in self.business_rules]
        return payload
