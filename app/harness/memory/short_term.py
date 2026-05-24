from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class MemoryMessage:
    def __init__(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.role = role
        self.content = content
        self.timestamp = datetime.now(timezone.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ShortTermMemory:
    def __init__(self) -> None:
        self._sessions: dict[str, list[MemoryMessage]] = {}

    def add_message(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        msg = MemoryMessage(role=role, content=content, metadata=metadata)
        self._sessions[session_id].append(msg)

    def get_messages(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 10
        if limit > 50:
            limit = 50
        messages = self._sessions.get(session_id, [])
        return [m.to_dict() for m in messages[-limit:]]

    def summarize(self, session_id: str, max_chars: int = 500) -> str:
        messages = self._sessions.get(session_id, [])
        if not messages:
            return ""
        parts = [f"[{m.role}] {m.content}" for m in messages]
        full = "\n".join(parts)
        if len(full) <= max_chars:
            return full
        return full[:max_chars] + "..."

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]

    def get_context(self, session_id: str) -> dict[str, Any]:
        messages = self._sessions.get(session_id, [])
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "summary": self.summarize(session_id),
        }

    def summary(self) -> dict[str, Any]:
        sessions: list[dict[str, Any]] = []
        total_messages = 0
        for sid, msgs in self._sessions.items():
            count = len(msgs)
            total_messages += count
            sessions.append({"session_id": sid, "message_count": count})
        return {
            "session_count": len(self._sessions),
            "message_count": total_messages,
            "sessions": sessions,
        }
