"""Request rate limiting helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Callable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Result returned by the rate limiter."""

    allowed: bool
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._time = time_func or time.time
        self._requests: dict[str, deque[float]] = {}

    def allow(self, key: str) -> RateLimitDecision:
        """Check whether a request can proceed for the given key."""
        now = self._time()
        window = self._requests.setdefault(key, deque())
        while window and now - window[0] >= self.window_seconds:
            window.popleft()
        if len(window) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - window[0])))
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
        window.append(now)
        return RateLimitDecision(allowed=True, retry_after_seconds=0)
