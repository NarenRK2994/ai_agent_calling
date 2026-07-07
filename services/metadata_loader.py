"""Metadata loading, validation, enrichment, and agent-consumption adapters."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from metadata_models import BusinessRuleMetadata, ColumnMetadata, MetadataVersion, RelationshipMetadata, TableMetadata
from retriever.models import ERPColumnMetadata, ERPRelationshipMetadata, ERPTableMetadata
from services.metadata_repository import MetadataRepository


class MetadataLoader:
    """Loads raw or enriched metadata, validates it, and adapts it for downstream consumers."""

    def __init__(self, repository: MetadataRepository) -> None:
        self.repository = repository

    def load_raw_tables(self) -> list[TableMetadata]:
        """Load raw metadata artifacts from the repository."""
        return [self._payload_to_table(payload) for payload in self.repository.load_raw_payloads()]

    def load_enriched_tables(self) -> list[TableMetadata]:
        """Load enriched metadata artifacts from the repository."""
        return [self._payload_to_table(payload) for payload in self.repository.load_enriched_payloads()]

    def enrich_tables(self, raw_tables: list[TableMetadata]) -> list[TableMetadata]:
        """Create enriched metadata while keeping raw metadata untouched on disk."""
        enriched_tables: list[TableMetadata] = []
        for table in raw_tables:
            important_columns = tuple(column.name for column in table.columns if self._is_important(column))
            approval_columns = tuple(column.name for column in table.columns if column.category == "Approval")
            payment_columns = tuple(column.name for column in table.columns if column.category == "Payment")
            audit_columns = tuple(
                column.name for column in table.columns if column.category in {"Audit", "Who Columns", "Dates"}
            )
            tax_columns = tuple(column.name for column in table.columns if column.category == "Tax")
            flexfields = tuple(column.name for column in table.columns if column.category == "Flexfield")
            global_flexfields = tuple(
                column.name for column in table.columns if column.category == "Global Flexfield"
            )
            common_filters = self._build_common_filters(table)
            enriched_tables.append(
                replace(
                    table,
                    business_description=table.description,
                    business_purpose=f"Supports {table.module.lower()} reporting and operational workflows.",
                    business_questions=self._build_business_questions(table),
                    common_filters=common_filters,
                    common_aggregations=self._build_common_aggregations(table),
                    common_joins=self._build_common_joins(table),
                    frequently_used_columns=important_columns,
                    important_columns=important_columns,
                    approval_columns=approval_columns,
                    payment_columns=payment_columns,
                    audit_columns=audit_columns,
                    tax_columns=tax_columns,
                    flexfields=flexfields,
                    global_flexfields=global_flexfields,
                )
            )
        return enriched_tables

    def validate_tables(self, tables: list[TableMetadata]) -> dict[str, Any]:
        """Validate metadata completeness and relationship consistency."""
        errors: list[str] = []
        warnings: list[str] = []
        for table in tables:
            if not table.primary_key:
                warnings.append(f"{table.owner}.{table.table}: missing primary key.")
            if not table.description.strip():
                warnings.append(f"{table.owner}.{table.table}: missing description.")

            seen_columns: set[str] = set()
            for column in table.columns:
                if column.name in seen_columns:
                    errors.append(f"{table.owner}.{table.table}: duplicate column {column.name}.")
                seen_columns.add(column.name)

            available_tables = {item.table for item in tables}
            for relationship in table.relationships:
                if relationship.referenced_table not in available_tables:
                    errors.append(
                        f"{table.owner}.{table.table}: broken relationship to {relationship.referenced_table}."
                    )
        return {
            "is_valid": not errors,
            "table_count": len(tables),
            "errors": errors,
            "warnings": warnings,
        }

    def build_agent_documents(self, tables: list[TableMetadata]) -> list[ERPTableMetadata]:
        """Adapt enriched enterprise metadata into the existing agent document contract."""
        documents: list[ERPTableMetadata] = []
        for table in tables:
            description_parts = [table.description]
            if table.business_purpose:
                description_parts.append(table.business_purpose)
            documents.append(
                ERPTableMetadata(
                    module=table.module,
                    table=table.table,
                    description=" ".join(part for part in description_parts if part),
                    primary_key=table.primary_key or "",
                    columns=tuple(
                        ERPColumnMetadata(
                            name=column.name,
                            description=self._build_column_description(column),
                        )
                        for column in table.columns
                    ),
                    relationships=tuple(
                        ERPRelationshipMetadata(
                            table=relationship.referenced_table,
                            join=relationship.join_column,
                        )
                        for relationship in table.relationships
                    ),
                    business_questions=table.business_questions,
                )
            )
        return documents

    def build_agent_payloads(self, tables: list[TableMetadata]) -> list[dict[str, Any]]:
        """Build legacy-compatible JSON payloads that the current agent can read unchanged."""
        payloads: list[dict[str, Any]] = []
        for table in tables:
            payloads.append(
                {
                    "module": table.module,
                    "table": table.table,
                    "description": " ".join(
                        part for part in (table.description, table.business_purpose) if part
                    ),
                    "primary_key": table.primary_key or "",
                    "columns": [
                        {
                            "name": column.name,
                            "description": self._build_column_description(column),
                        }
                        for column in table.columns
                    ],
                    "relationships": [
                        {
                            "table": relationship.referenced_table,
                            "join": relationship.join_column,
                        }
                        for relationship in table.relationships
                    ],
                    "business_questions": list(table.business_questions),
                    "owner": table.owner,
                    "business_description": table.business_description,
                    "common_filters": list(table.common_filters),
                    "common_aggregations": list(table.common_aggregations),
                    "important_columns": list(table.important_columns),
                }
            )
        return payloads

    def build_embedding_documents(self, tables: list[TableMetadata]) -> list[dict[str, Any]]:
        """Create rich text documents ready for embedding and ChromaDB indexing."""
        documents: list[dict[str, Any]] = []
        for table in tables:
            column_lines = [
                f"{column.name} ({column.data_type}, {column.category}): {column.description}"
                for column in table.columns
            ]
            relationship_lines = [
                f"{relationship.referenced_table}.{relationship.referenced_column} via {relationship.join_column}"
                for relationship in table.relationships
            ]
            text = "\n".join(
                [
                    f"Table: {table.table}",
                    f"Owner: {table.owner}",
                    f"Module: {table.module}",
                    f"Description: {table.description}",
                    f"Business Purpose: {table.business_purpose}",
                    f"Primary Key: {table.primary_key or 'None'}",
                    "Important Columns:",
                    *table.important_columns,
                    "Relationships:",
                    *relationship_lines,
                    "Business Questions:",
                    *table.business_questions,
                    "Columns:",
                    *column_lines,
                ]
            )
            documents.append(
                {
                    "id": table.document_id,
                    "text": text,
                    "metadata": {
                        "owner": table.owner,
                        "module": table.module,
                        "table": table.table,
                        "primary_key": table.primary_key or "",
                    },
                }
            )
        return documents

    def _payload_to_table(self, payload: dict[str, Any]) -> TableMetadata:
        """Convert a stored JSON payload into typed table metadata."""
        columns = tuple(
            ColumnMetadata(
                name=item["name"],
                description=item.get("description", ""),
                data_type=item.get("data_type", "VARCHAR2"),
                nullable=bool(item.get("nullable", True)),
                data_length=item.get("data_length"),
                data_precision=item.get("data_precision"),
                data_scale=item.get("data_scale"),
                default_value=item.get("default_value"),
                category=item.get("category", "Other"),
                is_primary_key=bool(item.get("is_primary_key", False)),
                is_foreign_key=bool(item.get("is_foreign_key", False)),
                referenced_table=item.get("referenced_table"),
                referenced_column=item.get("referenced_column"),
                business_rules=tuple(
                    BusinessRuleMetadata(
                        column_name=rule["column_name"],
                        value=rule["value"],
                        meaning=rule["meaning"],
                        source=rule["source"],
                    )
                    for rule in item.get("business_rules", [])
                ),
            )
            for item in payload.get("columns", [])
        )
        relationships = tuple(
            RelationshipMetadata(
                relationship_type=item["relationship_type"],
                join_column=item["join_column"],
                referenced_table=item["referenced_table"],
                referenced_column=item["referenced_column"],
                constraint_name=item.get("constraint_name"),
            )
            for item in payload.get("relationships", [])
        )
        version_payload = payload.get("metadata_version")
        version = None
        if version_payload:
            version = MetadataVersion(
                generated_at=version_payload["generated_at"],
                oracle_version=version_payload["oracle_version"],
                erp_version=version_payload["erp_version"],
                schema_version=version_payload["schema_version"],
                metadata_version=version_payload["metadata_version"],
            )
        return TableMetadata(
            table=payload["table"],
            owner=payload["owner"],
            module=payload.get("module", "Shared ERP"),
            description=payload.get("description", ""),
            primary_key=payload.get("primary_key"),
            columns=columns,
            relationships=relationships,
            foreign_keys=tuple(payload.get("foreign_keys", [])),
            indexes=tuple(payload.get("indexes", [])),
            business_description=payload.get("business_description", ""),
            business_purpose=payload.get("business_purpose", ""),
            business_questions=tuple(payload.get("business_questions", [])),
            common_filters=tuple(payload.get("common_filters", [])),
            common_aggregations=tuple(payload.get("common_aggregations", [])),
            common_joins=tuple(payload.get("common_joins", [])),
            frequently_used_columns=tuple(payload.get("frequently_used_columns", [])),
            important_columns=tuple(payload.get("important_columns", [])),
            approval_columns=tuple(payload.get("approval_columns", [])),
            payment_columns=tuple(payload.get("payment_columns", [])),
            audit_columns=tuple(payload.get("audit_columns", [])),
            tax_columns=tuple(payload.get("tax_columns", [])),
            flexfields=tuple(payload.get("flexfields", [])),
            global_flexfields=tuple(payload.get("global_flexfields", [])),
            metadata_version=version,
        )

    def _is_important(self, column: ColumnMetadata) -> bool:
        """Identify columns that should be highlighted for prompts and retrieval."""
        return (
            column.is_primary_key
            or column.category in {"Business", "Approval", "Payment", "Tax", "Currency", "Dates"}
            or column.name in {"INVOICE_NUM", "INVOICE_AMOUNT", "INVOICE_DATE", "VENDOR_ID", "ORG_ID"}
        )

    def _build_business_questions(self, table: TableMetadata) -> tuple[str, ...]:
        """Generate practical business questions from the table name and enriched columns."""
        questions = [
            f"Show records from {table.table}",
            f"Summarize {table.table} by key business dimensions",
        ]
        if any(column.name == "PAYMENT_STATUS_FLAG" for column in table.columns):
            questions.append("Show unpaid invoices")
        if any(column.name == "APPROVAL_STATUS" for column in table.columns):
            questions.append("Show items awaiting approval")
        if any(column.name == "VENDOR_ID" for column in table.columns):
            questions.append("Invoices by supplier")
        return tuple(dict.fromkeys(questions))

    def _build_common_filters(self, table: TableMetadata) -> tuple[str, ...]:
        """Generate reusable filter suggestions for prompt-building and SQL generation."""
        filters: list[str] = []
        available_columns = {column.name for column in table.columns}
        if "PAYMENT_STATUS_FLAG" in available_columns:
            filters.append("PAYMENT_STATUS_FLAG = 'N'")
        if "APPROVAL_STATUS" in available_columns:
            filters.append("APPROVAL_STATUS = 'APPROVED'")
        if "ORG_ID" in available_columns:
            filters.append("ORG_ID = :org_id")
        return tuple(filters)

    def _build_common_aggregations(self, table: TableMetadata) -> tuple[str, ...]:
        """Generate aggregation hints based on frequently useful ERP measures."""
        aggregations: list[str] = []
        available_columns = {column.name for column in table.columns}
        if "INVOICE_AMOUNT" in available_columns:
            aggregations.append("SUM(INVOICE_AMOUNT)")
        if "AMOUNT" in available_columns:
            aggregations.append("SUM(AMOUNT)")
        aggregations.append("COUNT(*)")
        return tuple(dict.fromkeys(aggregations))

    def _build_common_joins(self, table: TableMetadata) -> tuple[str, ...]:
        """Generate join hints from detected foreign-key relationships."""
        return tuple(
            f"{table.table}.{relationship.join_column} = {relationship.referenced_table}.{relationship.referenced_column}"
            for relationship in table.relationships
        )

    def _build_column_description(self, column: ColumnMetadata) -> str:
        """Create a retriever-friendly column description string."""
        parts = [column.description, f"Category: {column.category}", f"Data Type: {column.data_type}"]
        if column.business_rules:
            parts.append(
                "Rules: " + ", ".join(f"{rule.value}={rule.meaning}" for rule in column.business_rules)
            )
        return " | ".join(part for part in parts if part)
