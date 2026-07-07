"""Oracle database connector with pooling, retries, and read-only execution."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import Any, Protocol

import pandas as pd

from config import OracleConfig
from database.base import BaseDatabaseClient
from utils.exceptions import DatabaseConnectionError, DatabaseExecutionError


class OraclePoolLike(Protocol):
    """Protocol for test-friendly Oracle connection pools."""

    def acquire(self) -> Any:
        """Acquire a pooled database connection."""


class OracleDatabaseClient(BaseDatabaseClient):
    """Oracle database implementation for ERP data access."""

    def __init__(
        self,
        config: OracleConfig,
        *,
        pool: OraclePoolLike | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config
        self._pool = pool
        self._sleep = sleep_func or time.sleep

    @property
    def pool(self) -> OraclePoolLike:
        """Lazily initialize the Oracle connection pool."""
        if self._pool is None:
            self._pool = self._create_pool()
        return self._pool

    def execute_query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Execute a parameterized read-only query with retries and structured errors."""
        self._ensure_read_only_sql(sql)
        last_error: DatabaseExecutionError | None = None
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                return self._execute_once(sql, parameters or {})
            except DatabaseExecutionError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.config.retry_attempts:
                    raise
                self._sleep(self.config.retry_backoff_seconds * attempt)
        if last_error is not None:
            raise last_error
        raise DatabaseExecutionError(
            "Oracle query execution failed without a captured exception.",
            operation="execute_query",
        )

    def _execute_once(self, sql: str, parameters: dict[str, Any]) -> pd.DataFrame:
        """Perform one read-only SQL execution against a pooled connection."""
        try:
            with self.pool.acquire() as connection:
                self._set_connection_timeouts(connection)
                if self.config.read_only:
                    self._set_read_only_session(connection)
                with connection.cursor() as cursor:
                    cursor.execute(sql, parameters)
                    rows = cursor.fetchall()
                    columns = [column[0] for column in cursor.description or []]
                    return pd.DataFrame(rows, columns=columns)
        except DatabaseExecutionError:
            raise
        except Exception as exc:
            raise DatabaseExecutionError(
                f"Oracle query failed: {exc}",
                operation="execute_query",
                retryable=self._is_retryable_error(exc),
                error_code=getattr(exc, "code", None),
            ) from exc

    def _create_pool(self) -> OraclePoolLike:
        """Create a pooled Oracle client using python-oracledb."""
        try:
            import oracledb

            if self.config.thick_mode or self.config.client_lib_dir or self.config.config_dir:
                init_kwargs: dict[str, str] = {}
                if self.config.client_lib_dir:
                    init_kwargs["lib_dir"] = str(self.config.client_lib_dir)
                if self.config.config_dir:
                    init_kwargs["config_dir"] = str(self.config.config_dir)
                try:
                    oracledb.init_oracle_client(**init_kwargs)
                except Exception as exc:
                    raise DatabaseConnectionError(
                        f"Failed to enable Oracle Thick mode: {exc}",
                        operation="init_oracle_client",
                        retryable=False,
                        error_code=getattr(exc, "code", None),
                    ) from exc

            return oracledb.create_pool(
                user=self.config.username,
                password=self.config.password,
                dsn=self.config.dsn,
                min=self.config.min_connections,
                max=self.config.max_connections,
                increment=self.config.increment,
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:
            raise DatabaseConnectionError(
                f"Failed to initialize Oracle pool: {exc}",
                operation="create_pool",
                retryable=False,
                error_code=getattr(exc, "code", None),
            ) from exc

    def _ensure_read_only_sql(self, sql: str) -> None:
        """Enforce that only read-only SQL statements are sent to Oracle."""
        if not self.config.read_only:
            return
        normalized = sql.strip().upper()
        if not normalized.startswith(("SELECT", "WITH")):
            raise DatabaseExecutionError(
                "Read-only mode allows only SELECT or WITH statements.",
                operation="execute_query",
                retryable=False,
            )

    def _set_connection_timeouts(self, connection: Any) -> None:
        """Apply per-connection timeout settings when supported by the driver."""
        if hasattr(connection, "call_timeout"):
            connection.call_timeout = self.config.statement_timeout_ms

    def _set_read_only_session(self, connection: Any) -> None:
        """Set the Oracle session into read-only transaction mode when possible."""
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Classify common transient Oracle/driver failures as retryable."""
        message = str(exc).upper()
        retryable_markers = ("DPY-", "DPI-", "ORA-12170", "ORA-12541", "ORA-12514", "TIMEOUT")
        return any(marker in message for marker in retryable_markers)
