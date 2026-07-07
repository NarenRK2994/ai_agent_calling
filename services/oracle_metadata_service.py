"""Oracle Data Dictionary extraction service for enterprise ERP metadata."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from database.base import BaseDatabaseClient
from metadata_models import BusinessRuleMetadata, ColumnMetadata, MetadataVersion, RelationshipMetadata, TableMetadata


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OracleMetadataQuerySet:
    """Encapsulates the SQL used to query Oracle Data Dictionary metadata."""

    table_query: str = """
        SELECT owner, table_name
        FROM all_tables
        WHERE (:owner IS NULL OR owner = :owner)
        ORDER BY owner, table_name
    """
    column_query: str = """
        SELECT owner, table_name, column_name, data_type, nullable, data_length,
               data_precision, data_scale, data_default
        FROM all_tab_columns
        WHERE (:owner IS NULL OR owner = :owner)
        ORDER BY owner, table_name, column_id
    """
    table_comment_query: str = """
        SELECT owner, table_name, comments
        FROM all_tab_comments
        WHERE (:owner IS NULL OR owner = :owner)
    """
    column_comment_query: str = """
        SELECT owner, table_name, column_name, comments
        FROM all_col_comments
        WHERE (:owner IS NULL OR owner = :owner)
    """
    constraint_query: str = """
        SELECT owner, table_name, constraint_name, constraint_type, r_owner, r_constraint_name
        FROM all_constraints
        WHERE (:owner IS NULL OR owner = :owner)
          AND constraint_type IN ('P', 'R')
    """
    constraint_column_query: str = """
        SELECT owner, table_name, constraint_name, column_name, position
        FROM all_cons_columns
        WHERE (:owner IS NULL OR owner = :owner)
        ORDER BY owner, table_name, constraint_name, position
    """
    index_query: str = """
        SELECT table_owner AS owner, table_name, index_name
        FROM all_indexes
        WHERE (:owner IS NULL OR table_owner = :owner)
        ORDER BY table_owner, table_name, index_name
    """
    version_query: str = """
        SELECT banner
        FROM v$version
        WHERE banner LIKE 'Oracle Database%'
    """


class OracleMetadataService:
    """Extracts raw Oracle ERP metadata from the Oracle Data Dictionary."""

    def __init__(
        self,
        database_client: BaseDatabaseClient,
        *,
        query_set: OracleMetadataQuerySet | None = None,
        erp_version: str = "Oracle ERP",
        schema_version: str = "1.0",
        metadata_version: str = "1.0",
    ) -> None:
        self.database_client = database_client
        self.query_set = query_set or OracleMetadataQuerySet()
        self.erp_version = erp_version
        self.schema_version = schema_version
        self.metadata_version = metadata_version

    def extract_tables(self, owner: str | None = None) -> list[TableMetadata]:
        """Extract raw table metadata for every table visible in the Oracle schema."""
        params = {"owner": owner.upper() if owner else None}
        tables_df = self.database_client.execute_query(self.query_set.table_query, params)
        columns_df = self.database_client.execute_query(self.query_set.column_query, params)
        table_comments_df = self.database_client.execute_query(self.query_set.table_comment_query, params)
        column_comments_df = self.database_client.execute_query(self.query_set.column_comment_query, params)
        constraints_df = self.database_client.execute_query(self.query_set.constraint_query, params)
        constraint_columns_df = self.database_client.execute_query(self.query_set.constraint_column_query, params)
        indexes_df = self.database_client.execute_query(self.query_set.index_query, params)

        version = self._build_version()
        table_comments = {
            (row["OWNER"], row["TABLE_NAME"]): (row["COMMENTS"] or "")
            for _, row in table_comments_df.iterrows()
        }
        column_comments = {
            (row["OWNER"], row["TABLE_NAME"], row["COLUMN_NAME"]): (row["COMMENTS"] or "")
            for _, row in column_comments_df.iterrows()
        }
        index_map = defaultdict(list)
        for _, row in indexes_df.iterrows():
            index_map[(row["OWNER"], row["TABLE_NAME"])].append(row["INDEX_NAME"])

        constraint_rows = self._group_constraint_rows(constraints_df, constraint_columns_df)
        referenced_constraints = {
            (item["owner"], item["constraint_name"]): item
            for item in constraint_rows
        }

        table_metadata: list[TableMetadata] = []
        for _, table_row in tables_df.iterrows():
            owner_name = str(table_row["OWNER"]).upper()
            table_name = str(table_row["TABLE_NAME"]).upper()
            module = self._infer_module(table_name)
            description = table_comments.get((owner_name, table_name), "").strip() or f"{table_name} table."

            pk_columns = self._resolve_primary_key(constraint_rows, owner_name, table_name)
            columns = self._build_columns(
                owner_name,
                table_name,
                columns_df,
                column_comments,
                constraint_rows,
                referenced_constraints,
            )
            relationships = self._build_relationships(
                owner_name,
                table_name,
                constraint_rows,
                referenced_constraints,
            )
            table_metadata.append(
                TableMetadata(
                    table=table_name,
                    owner=owner_name,
                    module=module,
                    description=description,
                    primary_key=pk_columns[0] if pk_columns else None,
                    columns=tuple(columns),
                    relationships=tuple(relationships),
                    foreign_keys=tuple(sorted({relationship.join_column for relationship in relationships})),
                    indexes=tuple(index_map.get((owner_name, table_name), [])),
                    metadata_version=version,
                )
            )

        LOGGER.info("Extracted %s Oracle metadata tables from owner=%s", len(table_metadata), owner or "*")
        return table_metadata

    def _build_version(self) -> MetadataVersion:
        """Build version metadata describing the current extraction run."""
        try:
            version_df = self.database_client.execute_query(self.query_set.version_query)
            oracle_version = version_df.iloc[0]["BANNER"] if not version_df.empty else "Unknown Oracle Version"
        except Exception:
            oracle_version = "Unknown Oracle Version"
        return MetadataVersion(
            generated_at=datetime.now(timezone.utc).isoformat(),
            oracle_version=str(oracle_version),
            erp_version=self.erp_version,
            schema_version=self.schema_version,
            metadata_version=self.metadata_version,
        )

    def _group_constraint_rows(self, constraints_df: Any, constraint_columns_df: Any) -> list[dict[str, Any]]:
        """Merge Oracle constraints with their ordered column lists."""
        columns_by_constraint: dict[tuple[str, str], list[str]] = defaultdict(list)
        tables_by_constraint: dict[tuple[str, str], str] = {}
        for _, row in constraint_columns_df.iterrows():
            key = (str(row["OWNER"]).upper(), str(row["CONSTRAINT_NAME"]).upper())
            columns_by_constraint[key].append(str(row["COLUMN_NAME"]).upper())
            tables_by_constraint[key] = str(row["TABLE_NAME"]).upper()

        grouped: list[dict[str, Any]] = []
        for _, row in constraints_df.iterrows():
            owner = str(row["OWNER"]).upper()
            constraint_name = str(row["CONSTRAINT_NAME"]).upper()
            key = (owner, constraint_name)
            grouped.append(
                {
                    "owner": owner,
                    "table_name": str(row["TABLE_NAME"]).upper(),
                    "constraint_name": constraint_name,
                    "constraint_type": str(row["CONSTRAINT_TYPE"]).upper(),
                    "r_owner": str(row["R_OWNER"]).upper() if row["R_OWNER"] else None,
                    "r_constraint_name": str(row["R_CONSTRAINT_NAME"]).upper() if row["R_CONSTRAINT_NAME"] else None,
                    "columns": tuple(columns_by_constraint.get(key, [])),
                }
            )
        return grouped

    def _resolve_primary_key(self, constraint_rows: list[dict[str, Any]], owner: str, table_name: str) -> list[str]:
        """Return primary key columns for a table."""
        return [
            column
            for item in constraint_rows
            if item["owner"] == owner and item["table_name"] == table_name and item["constraint_type"] == "P"
            for column in item["columns"]
        ]

    def _build_columns(
        self,
        owner: str,
        table_name: str,
        columns_df: Any,
        column_comments: dict[tuple[str, str, str], str],
        constraint_rows: list[dict[str, Any]],
        referenced_constraints: dict[tuple[str, str], dict[str, Any]],
    ) -> list[ColumnMetadata]:
        """Create rich column metadata entries for a table."""
        pk_columns = set(self._resolve_primary_key(constraint_rows, owner, table_name))
        fk_lookup: dict[str, tuple[str, str]] = {}
        for item in constraint_rows:
            if item["owner"] != owner or item["table_name"] != table_name or item["constraint_type"] != "R":
                continue
            reference = referenced_constraints.get((item["r_owner"], item["r_constraint_name"]))
            if reference is None:
                continue
            for position, column_name in enumerate(item["columns"]):
                referenced_column = reference["columns"][position] if position < len(reference["columns"]) else ""
                fk_lookup[column_name] = (reference["table_name"], referenced_column)

        table_columns = columns_df[
            (columns_df["OWNER"] == owner) &
            (columns_df["TABLE_NAME"] == table_name)
        ]
        columns: list[ColumnMetadata] = []
        for _, row in table_columns.iterrows():
            column_name = str(row["COLUMN_NAME"]).upper()
            referenced_table, referenced_column = fk_lookup.get(column_name, (None, None))
            category = self._categorize_column(column_name)
            rules = self._build_business_rules(column_name)
            description = column_comments.get((owner, table_name, column_name), "").strip() or f"{column_name} column."
            columns.append(
                ColumnMetadata(
                    name=column_name,
                    description=description,
                    data_type=str(row["DATA_TYPE"]).upper(),
                    nullable=str(row["NULLABLE"]).upper() == "Y",
                    data_length=int(row["DATA_LENGTH"]) if row["DATA_LENGTH"] is not None else None,
                    data_precision=int(row["DATA_PRECISION"]) if row["DATA_PRECISION"] is not None else None,
                    data_scale=int(row["DATA_SCALE"]) if row["DATA_SCALE"] is not None else None,
                    default_value=str(row["DATA_DEFAULT"]).strip() if row["DATA_DEFAULT"] else None,
                    category=category,
                    is_primary_key=column_name in pk_columns,
                    is_foreign_key=column_name in fk_lookup,
                    referenced_table=referenced_table,
                    referenced_column=referenced_column,
                    business_rules=tuple(rules),
                )
            )
        return columns

    def _build_relationships(
        self,
        owner: str,
        table_name: str,
        constraint_rows: list[dict[str, Any]],
        referenced_constraints: dict[tuple[str, str], dict[str, Any]],
    ) -> list[RelationshipMetadata]:
        """Build relationship metadata from foreign-key constraints."""
        relationships: list[RelationshipMetadata] = []
        for item in constraint_rows:
            if item["owner"] != owner or item["table_name"] != table_name or item["constraint_type"] != "R":
                continue
            reference = referenced_constraints.get((item["r_owner"], item["r_constraint_name"]))
            if reference is None:
                continue
            for position, column_name in enumerate(item["columns"]):
                referenced_column = reference["columns"][position] if position < len(reference["columns"]) else column_name
                relationships.append(
                    RelationshipMetadata(
                        relationship_type="FOREIGN_KEY",
                        join_column=column_name,
                        referenced_table=reference["table_name"],
                        referenced_column=referenced_column,
                        constraint_name=item["constraint_name"],
                    )
                )
        return relationships

    def _infer_module(self, table_name: str) -> str:
        """Infer an Oracle ERP module from common table prefixes."""
        prefix_map = {
            "AP_": "Accounts Payable",
            "AR_": "Accounts Receivable",
            "PO_": "Purchasing",
            "GL_": "General Ledger",
            "HZ_": "Trading Community",
            "XLA_": "Subledger Accounting",
            "MTL_": "Inventory",
            "RCV_": "Receiving",
            "OE_": "Order Management",
            "PA_": "Project Accounting",
        }
        for prefix, module in prefix_map.items():
            if table_name.startswith(prefix):
                return module
        return "Shared ERP"

    def _categorize_column(self, column_name: str) -> str:
        """Classify a column into an Oracle ERP-friendly business category."""
        upper_name = column_name.upper()
        if upper_name.endswith("_ID"):
            return "Foreign Key" if upper_name not in {"ROWID"} else "Other"
        if upper_name in {"CREATED_BY", "CREATION_DATE", "LAST_UPDATED_BY", "LAST_UPDATE_DATE", "LAST_UPDATE_LOGIN"}:
            return "Who Columns"
        if upper_name.startswith("ATTRIBUTE"):
            return "Flexfield"
        if upper_name.startswith("GLOBAL_ATTRIBUTE"):
            return "Global Flexfield"
        if "APPROVAL" in upper_name:
            return "Approval"
        if "PAYMENT" in upper_name or "PAID" in upper_name:
            return "Payment"
        if "TAX" in upper_name:
            return "Tax"
        if "PROJECT" in upper_name or upper_name.startswith("TASK_"):
            return "Project Accounting"
        if "CURRENCY" in upper_name or upper_name.endswith("_RATE"):
            return "Currency"
        if upper_name.endswith("_DATE"):
            return "Dates"
        if upper_name in {"ORG_ID", "SET_OF_BOOKS_ID", "LEDGER_ID"}:
            return "Business"
        return "Other"

    def _build_business_rules(self, column_name: str) -> list[BusinessRuleMetadata]:
        """Attach common ERP business meanings for well-known coded columns."""
        rule_map = {
            "PAYMENT_STATUS_FLAG": (
                ("Y", "Paid"),
                ("N", "Unpaid"),
                ("P", "Partially Paid"),
            ),
            "APPROVAL_STATUS": (
                ("APPROVED", "Approved"),
                ("NEEDS REAPPROVAL", "Needs Reapproval"),
                ("NEVER APPROVED", "Never Approved"),
            ),
        }
        rules = rule_map.get(column_name.upper(), ())
        return [
            BusinessRuleMetadata(
                column_name=column_name.upper(),
                value=value,
                meaning=meaning,
                source="Seeded ERP rule map",
            )
            for value, meaning in rules
        ]
