"""Install-ready unit tests for the Oracle connector."""

from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas is not installed in this environment")
class OracleConnectorTests(unittest.TestCase):
    """Verifies pooled read-only execution using fake Oracle objects."""

    def test_execute_query_returns_dataframe(self) -> None:
        from config import OracleConfig
        from database.oracle import OracleDatabaseClient

        class FakeCursor:
            description = [("INVOICE_ID",), ("AMOUNT",)]

            def execute(self, sql, parameters=None):  # type: ignore[no-untyped-def]
                self.sql = sql
                self.parameters = parameters

            def fetchall(self):  # type: ignore[no-untyped-def]
                return [(1, 10.5), (2, 20.0)]

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                return None

        class FakeConnection:
            def __init__(self) -> None:
                self.call_timeout = None
                self.commands: list[str] = []

            def cursor(self):  # type: ignore[no-untyped-def]
                parent = self

                class CursorFactory(FakeCursor):
                    def execute(self, sql, parameters=None):  # type: ignore[no-untyped-def]
                        parent.commands.append(sql)
                        super().execute(sql, parameters)

                return CursorFactory()

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                return None

        class FakePool:
            def acquire(self):  # type: ignore[no-untyped-def]
                return FakeConnection()

        config = OracleConfig(
            username="user",
            password="pw",
            dsn="dsn",
            min_connections=1,
            max_connections=2,
            increment=1,
            timeout_seconds=30,
            statement_timeout_ms=5000,
            retry_attempts=1,
            retry_backoff_seconds=0.0,
            read_only=True,
            client_lib_dir=None,
        )
        client = OracleDatabaseClient(config=config, pool=FakePool())
        dataframe = client.execute_query("SELECT INVOICE_ID, AMOUNT FROM AP_INVOICES_ALL WHERE INVOICE_ID = :invoice_id", {"invoice_id": 1})

        self.assertEqual(["INVOICE_ID", "AMOUNT"], list(dataframe.columns))
        self.assertEqual(2, len(dataframe))


if __name__ == "__main__":
    unittest.main()
