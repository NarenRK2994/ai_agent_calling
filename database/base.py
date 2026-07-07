"""Base abstractions for database integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseDatabaseClient(ABC):
    """Contract for read-only database clients."""

    @abstractmethod
    def execute_query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Execute a read-only SQL query and return rows as a DataFrame."""
