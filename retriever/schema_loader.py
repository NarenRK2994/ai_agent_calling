"""Metadata loading, validation, and search helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retriever.exceptions import MetadataValidationError
from retriever.models import ERPColumnMetadata, ERPRelationshipMetadata, ERPTableMetadata


class MetadataSchemaValidator:
    """Validates raw JSON metadata before it is converted into dataclasses."""

    REQUIRED_TOP_LEVEL_FIELDS = {
        "module": str,
        "table": str,
        "description": str,
        "primary_key": str,
        "columns": list,
        "relationships": list,
        "business_questions": list,
    }

    def validate(self, payload: dict[str, Any], source: Path | None = None) -> dict[str, Any]:
        """Validate a raw metadata payload and return it unchanged if valid."""
        source_label = str(source) if source else "<memory>"
        for field_name, expected_type in self.REQUIRED_TOP_LEVEL_FIELDS.items():
            if field_name not in payload:
                raise MetadataValidationError(
                    f"Missing required field '{field_name}' in {source_label}"
                )
            if not isinstance(payload[field_name], expected_type):
                raise MetadataValidationError(
                    f"Field '{field_name}' in {source_label} must be of type "
                    f"{expected_type.__name__}"
                )

        self._validate_columns(payload["columns"], source_label)
        self._validate_relationships(payload["relationships"], source_label)
        self._validate_business_questions(payload["business_questions"], source_label)
        return payload

    def _validate_columns(self, columns: list[Any], source_label: str) -> None:
        """Validate each column entry in the metadata payload."""
        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                raise MetadataValidationError(
                    f"Column at index {index} in {source_label} must be an object"
                )
            self._require_string_key(column, "name", f"columns[{index}]", source_label)
            self._require_string_key(column, "description", f"columns[{index}]", source_label)

    def _validate_relationships(self, relationships: list[Any], source_label: str) -> None:
        """Validate each relationship entry in the metadata payload."""
        for index, relationship in enumerate(relationships):
            if not isinstance(relationship, dict):
                raise MetadataValidationError(
                    f"Relationship at index {index} in {source_label} must be an object"
                )
            self._require_string_key(relationship, "table", f"relationships[{index}]", source_label)
            self._require_string_key(relationship, "join", f"relationships[{index}]", source_label)

    def _validate_business_questions(self, questions: list[Any], source_label: str) -> None:
        """Ensure business questions are represented as strings."""
        for index, question in enumerate(questions):
            if not isinstance(question, str) or not question.strip():
                raise MetadataValidationError(
                    f"Business question at index {index} in {source_label} must be a non-empty string"
                )

    def _require_string_key(
        self,
        payload: dict[str, Any],
        key: str,
        context: str,
        source_label: str,
    ) -> None:
        """Ensure a nested payload contains a non-empty string for the given key."""
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise MetadataValidationError(
                f"Field '{context}.{key}' in {source_label} must be a non-empty string"
            )


class SchemaLoader:
    """Loads, validates, indexes, and searches ERP table metadata."""

    def __init__(self, validator: MetadataSchemaValidator | None = None) -> None:
        self.validator = validator or MetadataSchemaValidator()
        self._documents: list[ERPTableMetadata] = []
        self._by_table: dict[str, ERPTableMetadata] = {}

    def load(self, metadata_dir: Path) -> list[ERPTableMetadata]:
        """Read and validate every JSON metadata file under the target directory."""
        documents: list[ERPTableMetadata] = []
        for path in sorted(metadata_dir.rglob("*.json")):
            documents.append(self.load_file(path))
        self._documents = documents
        self._by_table = {document.table.upper(): document for document in documents}
        return list(self._documents)

    def load_file(self, path: Path) -> ERPTableMetadata:
        """Read one JSON file, validate it, and convert it into a dataclass."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.validator.validate(payload, source=path)
        return self._to_dataclass(payload, source_path=path)

    def get_by_table(self, table_name: str) -> ERPTableMetadata | None:
        """Return one table by name using a case-insensitive lookup."""
        return self._by_table.get(table_name.upper())

    def filter_by_module(self, module_name: str) -> list[ERPTableMetadata]:
        """Return all loaded tables belonging to a specific ERP module."""
        module_key = module_name.casefold()
        return [document for document in self._documents if document.module.casefold() == module_key]

    def search(
        self,
        text: str,
        *,
        module: str | None = None,
        limit: int | None = None,
    ) -> list[ERPTableMetadata]:
        """Search loaded documents across tables, descriptions, columns, and business questions."""
        query = text.casefold()
        candidates = self._documents
        if module is not None:
            module_key = module.casefold()
            candidates = [
                document for document in candidates if document.module.casefold() == module_key
            ]

        matches = [document for document in candidates if self._matches(document, query)]
        if limit is None:
            return matches
        return matches[:limit]

    def list_documents(self) -> list[ERPTableMetadata]:
        """Return a shallow copy of the currently loaded metadata documents."""
        return list(self._documents)

    def _matches(self, document: ERPTableMetadata, query: str) -> bool:
        """Check whether the query appears anywhere meaningful in a document."""
        searchable_parts = [
            document.module,
            document.table,
            document.description,
            document.primary_key,
            *[column.name for column in document.columns],
            *[column.description for column in document.columns],
            *[relationship.table for relationship in document.relationships],
            *[relationship.join for relationship in document.relationships],
            *document.business_questions,
        ]
        return any(query in part.casefold() for part in searchable_parts)

    def _to_dataclass(self, payload: dict[str, Any], source_path: Path) -> ERPTableMetadata:
        """Convert a validated JSON payload into a typed ERP metadata dataclass."""
        return ERPTableMetadata(
            module=payload["module"].strip(),
            table=payload["table"].strip().upper(),
            description=payload["description"].strip(),
            primary_key=payload["primary_key"].strip().upper(),
            columns=tuple(
                ERPColumnMetadata(
                    name=column["name"].strip().upper(),
                    description=column["description"].strip(),
                )
                for column in payload["columns"]
            ),
            relationships=tuple(
                ERPRelationshipMetadata(
                    table=relationship["table"].strip().upper(),
                    join=relationship["join"].strip().upper(),
                )
                for relationship in payload["relationships"]
            ),
            business_questions=tuple(
                question.strip() for question in payload["business_questions"]
            ),
            source_path=source_path,
        )
