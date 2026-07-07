"""Table metadata models for Oracle ERP schema extraction and enrichment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from metadata_models.column import ColumnMetadata
from metadata_models.relationship import RelationshipMetadata


@dataclass(frozen=True, slots=True)
class MetadataVersion:
    """Stores generation and source-system version details for one metadata artifact."""

    generated_at: str
    oracle_version: str
    erp_version: str
    schema_version: str
    metadata_version: str

    def to_dict(self) -> dict[str, str]:
        """Serialize version details into a JSON-friendly mapping."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Represents complete raw or enriched metadata for one Oracle ERP table."""

    table: str
    owner: str
    module: str
    description: str
    primary_key: str | None
    columns: tuple[ColumnMetadata, ...] = field(default_factory=tuple)
    relationships: tuple[RelationshipMetadata, ...] = field(default_factory=tuple)
    foreign_keys: tuple[str, ...] = field(default_factory=tuple)
    indexes: tuple[str, ...] = field(default_factory=tuple)
    business_description: str = ""
    business_purpose: str = ""
    business_questions: tuple[str, ...] = field(default_factory=tuple)
    common_filters: tuple[str, ...] = field(default_factory=tuple)
    common_aggregations: tuple[str, ...] = field(default_factory=tuple)
    common_joins: tuple[str, ...] = field(default_factory=tuple)
    frequently_used_columns: tuple[str, ...] = field(default_factory=tuple)
    important_columns: tuple[str, ...] = field(default_factory=tuple)
    approval_columns: tuple[str, ...] = field(default_factory=tuple)
    payment_columns: tuple[str, ...] = field(default_factory=tuple)
    audit_columns: tuple[str, ...] = field(default_factory=tuple)
    tax_columns: tuple[str, ...] = field(default_factory=tuple)
    flexfields: tuple[str, ...] = field(default_factory=tuple)
    global_flexfields: tuple[str, ...] = field(default_factory=tuple)
    metadata_version: MetadataVersion | None = None

    @property
    def document_id(self) -> str:
        """Return a stable identifier suitable for persistence or embeddings."""
        return f"{self.owner}.{self.table}"

    def to_dict(self) -> dict[str, object]:
        """Serialize the table metadata into a JSON-friendly mapping."""
        payload = asdict(self)
        payload["columns"] = [column.to_dict() for column in self.columns]
        payload["relationships"] = [relationship.to_dict() for relationship in self.relationships]
        payload["metadata_version"] = (
            self.metadata_version.to_dict() if self.metadata_version is not None else None
        )
        return payload
