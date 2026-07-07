"""Shared runtime service container."""

from __future__ import annotations

from dataclasses import dataclass

from utils.cache import TTLCache
from utils.history import ConversationMemoryStore, ExecutionLogStore, SQLHistoryStore
from utils.metrics import MetricsCollector
from utils.observability import ObservabilityManager
from utils.prompt_versioning import PromptVersionManager
from utils.rate_limit import SlidingWindowRateLimiter


@dataclass(slots=True)
class RuntimeServices:
    """Bundled runtime services used across workflow nodes."""

    cache: TTLCache[object]
    conversation_memory: ConversationMemoryStore
    sql_history: SQLHistoryStore
    execution_logs: ExecutionLogStore
    metrics: MetricsCollector
    prompt_versions: PromptVersionManager
    rate_limiter: SlidingWindowRateLimiter
    observability: ObservabilityManager
