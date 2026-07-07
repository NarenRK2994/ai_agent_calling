"""SQL validation helpers for Oracle ERP queries."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError


BLOCKED_SQL_KEYWORDS = {
    "DELETE",
    "UPDATE",
    "INSERT",
    "DROP",
    "TRUNCATE",
    "MERGE",
    "ALTER",
    "EXECUTE",
}


@dataclass(frozen=True, slots=True)
class SQLValidationResult:
    """Structured output returned by the SQL validator."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    normalized_sql: str | None = None


class SQLValidator:
    """Validates generated SQL against retrieved ERP schema and safety rules."""

    def validate(self, sql: str, schema_items: list[dict[str, Any]]) -> SQLValidationResult:
        """Validate syntax, table usage, columns, joins, and disallowed statements."""
        stripped_sql = sql.strip()
        keyword_errors = self._validate_statement_type(stripped_sql)
        if keyword_errors:
            return SQLValidationResult(is_valid=False, errors=keyword_errors)

        try:
            parsed = parse_one(stripped_sql, read="oracle")
        except ParseError as exc:
            return SQLValidationResult(
                is_valid=False,
                errors=[f"SQL syntax error: {exc}"],
            )

        errors: list[str] = []
        schema_by_table = {item["table"].upper(): item for item in schema_items}
        alias_to_table = self._collect_aliases(parsed)

        errors.extend(self._validate_tables(parsed, schema_by_table))
        errors.extend(self._validate_columns(parsed, schema_by_table, alias_to_table))
        errors.extend(self._validate_relationships(parsed, schema_by_table, alias_to_table))

        return SQLValidationResult(
            is_valid=not errors,
            errors=errors,
            normalized_sql=parsed.sql(dialect="oracle") if not errors else None,
        )

    def _validate_statement_type(self, sql: str) -> list[str]:
        """Reject mutating SQL and allow only SELECT or WITH statements."""
        upper_sql = sql.upper()
        for keyword in BLOCKED_SQL_KEYWORDS:
            if re.search(rf"\b{keyword}\b", upper_sql):
                return [f"Disallowed SQL keyword detected: {keyword}. Only read-only queries are allowed."]
        if not upper_sql.startswith(("SELECT", "WITH")):
            return ["Only SELECT or WITH queries are allowed."]
        return []

    def _validate_tables(
        self,
        parsed: exp.Expression,
        schema_by_table: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Ensure every referenced table exists in the retrieved ERP schema."""
        errors: list[str] = []
        for table in parsed.find_all(exp.Table):
            table_name = table.name.upper()
            if table_name not in schema_by_table:
                errors.append(
                    f"Unknown table '{table_name}'. The SQL must use only retrieved ERP tables."
                )
        return errors

    def _validate_columns(
        self,
        parsed: exp.Expression,
        schema_by_table: dict[str, dict[str, Any]],
        alias_to_table: dict[str, str],
    ) -> list[str]:
        """Ensure every referenced column exists and that unqualified columns are not ambiguous."""
        errors: list[str] = []
        allowed_columns = {
            table_name: {column.upper() for column in item.get("columns", [])}
            for table_name, item in schema_by_table.items()
        }
        for column in parsed.find_all(exp.Column):
            column_name = column.name.upper()
            table_alias = column.table.upper() if column.table else None
            if table_alias:
                table_name = alias_to_table.get(table_alias, table_alias)
                if table_name not in allowed_columns or column_name not in allowed_columns[table_name]:
                    errors.append(
                        f"Unknown column '{column.sql()}'. Column '{column_name}' is not available in table '{table_name}'."
                    )
                continue

            matching_tables = [
                table_name
                for table_name, columns in allowed_columns.items()
                if column_name in columns
            ]
            if not matching_tables:
                errors.append(
                    f"Unknown column '{column_name}'. It does not exist in the retrieved schema."
                )
            elif len(matching_tables) > 1:
                errors.append(
                    f"Ambiguous column '{column_name}'. Qualify it with a table alias."
                )
        return errors

    def _validate_relationships(
        self,
        parsed: exp.Expression,
        schema_by_table: dict[str, dict[str, Any]],
        alias_to_table: dict[str, str],
    ) -> list[str]:
        """Ensure join conditions align with known table relationships and join keys."""
        errors: list[str] = []
        relationship_map = self._build_relationship_map(schema_by_table)
        for join in parsed.find_all(exp.Join):
            joined_table_name = self._extract_joined_table(join)
            if joined_table_name is None:
                continue

            on_expression = join.args.get("on")
            if on_expression is None:
                errors.append(
                    f"Join with table '{joined_table_name}' is missing an ON condition."
                )
                continue

            comparisons = list(on_expression.find_all(exp.EQ))
            if not comparisons:
                errors.append(
                    f"Join with table '{joined_table_name}' must use an equality join on known keys."
                )
                continue

            if not any(
                self._is_valid_join_comparison(comparison, relationship_map, alias_to_table)
                for comparison in comparisons
            ):
                errors.append(
                    f"Join with table '{joined_table_name}' does not match any known relationship join key."
                )
        return errors

    def _collect_aliases(self, parsed: exp.Expression) -> dict[str, str]:
        """Build a lookup from alias name to actual table name."""
        aliases: dict[str, str] = {}
        for table in parsed.find_all(exp.Table):
            table_name = table.name.upper()
            aliases[table_name] = table_name
            alias = table.alias
            if alias:
                aliases[alias.upper()] = table_name
        return aliases

    def _build_relationship_map(
        self,
        schema_by_table: dict[str, dict[str, Any]],
    ) -> set[tuple[str, str, str]]:
        """Create a symmetric lookup of allowed table-to-table join keys."""
        relationships: set[tuple[str, str, str]] = set()
        for table_name, item in schema_by_table.items():
            for relationship in item.get("relationships", []):
                related_table = relationship["table"].upper()
                join_key = relationship["join"].upper()
                relationships.add((table_name, related_table, join_key))
                relationships.add((related_table, table_name, join_key))
        return relationships

    def _is_valid_join_comparison(
        self,
        comparison: exp.EQ,
        relationship_map: set[tuple[str, str, str]],
        alias_to_table: dict[str, str],
    ) -> bool:
        """Check whether one equality comparison matches a known relationship definition."""
        left = comparison.left
        right = comparison.right
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            return False
        left_table = alias_to_table.get(left.table.upper(), left.table.upper()) if left.table else ""
        right_table = alias_to_table.get(right.table.upper(), right.table.upper()) if right.table else ""
        if not left_table or not right_table:
            return False
        if left.name.upper() != right.name.upper():
            return False
        return (left_table, right_table, left.name.upper()) in relationship_map

    def _extract_joined_table(self, join: exp.Join) -> str | None:
        """Return the joined table name when it can be resolved from the AST."""
        joined = join.this
        if isinstance(joined, exp.Table):
            return joined.name.upper()
        return None
