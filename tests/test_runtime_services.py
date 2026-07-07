"""Unit tests for runtime support services."""

from __future__ import annotations

import unittest

from graph.state import ERPAgentState
from graph.workflow import _next_after_validation
from utils.cache import TTLCache
from utils.history import ConversationMemoryStore, SQLHistoryStore
from utils.rate_limit import SlidingWindowRateLimiter


class RuntimeServiceTests(unittest.TestCase):
    """Verifies cache, memory, history, rate limiting, and retry routing."""

    def test_ttl_cache_expires_entries(self) -> None:
        clock = {"now": 0.0}
        cache = TTLCache[str](ttl_seconds=5, time_func=lambda: clock["now"])
        cache.set("key", "value")

        self.assertEqual("value", cache.get("key"))
        clock["now"] = 6.0
        self.assertIsNone(cache.get("key"))

    def test_conversation_memory_trims_old_turns(self) -> None:
        store = ConversationMemoryStore(max_turns=2)
        store.append("session", "user", "one")
        store.append("session", "assistant", "two")
        store.append("session", "user", "three")

        turns = store.get("session")
        self.assertEqual(2, len(turns))
        self.assertEqual("two", turns[0].content)
        self.assertEqual("three", turns[1].content)

    def test_sql_history_keeps_latest_entries(self) -> None:
        store = SQLHistoryStore(limit=2)
        store.record("q1", "select 1 from dual", "generated")
        store.record("q2", "select 2 from dual", "executed")
        store.record("q3", "select 3 from dual", "executed")

        entries = store.list_entries()
        self.assertEqual(2, len(entries))
        self.assertEqual("q2", entries[0].question)
        self.assertEqual("q3", entries[1].question)

    def test_rate_limiter_blocks_when_window_is_full(self) -> None:
        clock = {"now": 0.0}
        limiter = SlidingWindowRateLimiter(
            max_requests=2,
            window_seconds=10,
            time_func=lambda: clock["now"],
        )

        self.assertTrue(limiter.allow("session").allowed)
        self.assertTrue(limiter.allow("session").allowed)
        blocked = limiter.allow("session")
        self.assertFalse(blocked.allowed)
        self.assertGreaterEqual(blocked.retry_after_seconds, 1)

    def test_validation_router_retries_then_finishes(self) -> None:
        retry_state = ERPAgentState(user_question="q", retry_requested=True)
        finish_state = ERPAgentState(user_question="q", retry_requested=False)
        execute_state = ERPAgentState(user_question="q", validated_sql="select 1 from dual")

        self.assertEqual("retry", _next_after_validation(retry_state))
        self.assertEqual("finish", _next_after_validation(finish_state))
        self.assertEqual("execute", _next_after_validation(execute_state))


if __name__ == "__main__":
    unittest.main()
