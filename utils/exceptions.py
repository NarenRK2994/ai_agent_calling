"""Shared exception types for the ERP AI Agent."""

from __future__ import annotations


class ERPAgentError(Exception):
    """Base application exception."""


class ConfigurationError(ERPAgentError):
    """Raised when configuration is invalid or incomplete."""


class ValidationError(ERPAgentError):
    """Raised when generated SQL fails validation."""


class WorkflowError(ERPAgentError):
    """Raised when the workflow cannot complete a request."""


class RateLimitError(ERPAgentError):
    """Raised when a caller exceeds the configured request rate limit."""


class DatabaseError(ERPAgentError):
    """Base exception for Oracle database errors."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        retryable: bool = False,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.retryable = retryable
        self.error_code = error_code


class DatabaseConnectionError(DatabaseError):
    """Raised when the Oracle connection pool cannot be created or used."""


class DatabaseExecutionError(DatabaseError):
    """Raised when a SQL statement fails during execution."""
