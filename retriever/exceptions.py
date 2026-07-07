"""Custom exceptions for retrieval and indexing components."""

from __future__ import annotations


class MetadataValidationError(ValueError):
    """Raised when a metadata JSON file does not match the expected structure."""
