"""Lightweight metrics collection helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class MetricsSnapshot:
    """Serializable metrics snapshot."""

    counters: dict[str, int] = field(default_factory=dict)
    timings: dict[str, list[float]] = field(default_factory=dict)


class MetricsCollector:
    """Tracks counters and durations for workflow observability."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._timings: dict[str, list[float]] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """Increase a named counter."""
        self._counters[name] = self._counters.get(name, 0) + value

    def observe(self, name: str, duration_seconds: float) -> None:
        """Record one duration measurement."""
        self._timings.setdefault(name, []).append(duration_seconds)

    def time_block(self, name: str) -> "_MetricsTimer":
        """Return a context manager that times one code block."""
        return _MetricsTimer(self, name)

    def snapshot(self) -> MetricsSnapshot:
        """Return a copy of the current metrics values."""
        return MetricsSnapshot(
            counters=dict(self._counters),
            timings={key: list(values) for key, values in self._timings.items()},
        )


class _MetricsTimer:
    """Context manager used by MetricsCollector.time_block."""

    def __init__(self, collector: MetricsCollector, name: str) -> None:
        self.collector = collector
        self.name = name
        self.started_at = 0.0

    def __enter__(self) -> "_MetricsTimer":
        self.started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.collector.observe(self.name, time.perf_counter() - self.started_at)
