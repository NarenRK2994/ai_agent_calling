"""Conversation memory, SQL history, and execution logging helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """Represents one user/assistant exchange in memory."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class SQLHistoryEntry:
    """Stores one generated or executed SQL statement."""

    question: str
    sql: str
    status: str


@dataclass(frozen=True, slots=True)
class ExecutionLogEntry:
    """Represents one workflow execution event."""

    stage: str
    status: str
    details: dict[str, Any]


class ConversationMemoryStore:
    """Maintains a rolling in-memory conversation history per session."""

    def __init__(self, max_turns: int) -> None:
        self.max_turns = max_turns
        self._sessions: dict[str, list[ConversationTurn]] = {}

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append one turn and trim the session to the configured history size."""
        turns = self._sessions.setdefault(session_id, [])
        turns.append(ConversationTurn(role=role, content=content))
        if len(turns) > self.max_turns:
            del turns[: len(turns) - self.max_turns]

    def get(self, session_id: str) -> list[ConversationTurn]:
        """Return the stored turns for one session."""
        return list(self._sessions.get(session_id, []))


class SQLHistoryStore:
    """Keeps a bounded history of SQL generations and executions."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._entries: list[SQLHistoryEntry] = []

    def record(self, question: str, sql: str, status: str) -> None:
        """Append one SQL history entry and keep the newest items only."""
        self._entries.append(SQLHistoryEntry(question=question, sql=sql, status=status))
        if len(self._entries) > self.limit:
            del self._entries[: len(self._entries) - self.limit]

    def list_entries(self) -> list[SQLHistoryEntry]:
        """Return the SQL history entries."""
        return list(self._entries)


class ExecutionLogStore:
    """Stores structured execution logs in memory and optionally on disk."""

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path
        self._entries: list[ExecutionLogEntry] = []

    def record(self, stage: str, status: str, **details: Any) -> None:
        """Capture one structured execution log entry."""
        entry = ExecutionLogEntry(stage=stage, status=status, details=details)
        self._entries.append(entry)
        if self.file_path is not None:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(entry)) + "\n")

    def list_entries(self) -> list[ExecutionLogEntry]:
        """Return all captured execution log entries."""
        return list(self._entries)
