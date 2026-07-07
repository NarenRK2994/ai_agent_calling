"""Business rule metadata used to enrich Oracle ERP columns."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class BusinessRuleMetadata:
    """Represents a business-facing meaning for a coded database value."""

    column_name: str
    value: str
    meaning: str
    source: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the business rule into a JSON-friendly mapping."""
        return asdict(self)
