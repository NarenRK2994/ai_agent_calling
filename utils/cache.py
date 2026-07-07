"""Simple in-memory TTL cache."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    """Represents one cached value with its expiration timestamp."""

    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Small unit-test-friendly in-memory TTL cache."""

    def __init__(self, ttl_seconds: int, *, time_func: Callable[[], float] | None = None) -> None:
        self.ttl_seconds = ttl_seconds
        self._time = time_func or time.time
        self._items: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        """Return a cached value when present and not expired."""
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        """Insert or replace a cached value."""
        self._items[key] = CacheEntry(value=value, expires_at=self._time() + self.ttl_seconds)

    def clear(self) -> None:
        """Remove all cache entries."""
        self._items.clear()
