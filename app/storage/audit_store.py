from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any

from app.models.schemas import AuditEvent


class SQLiteAuditStore:
    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from app.core.config import settings
            db_path = getattr(settings, "runtime_db_path", None) or os.path.join(
                "data", "db", "runtime.sqlite"
            )
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        dir_name = os.path.dirname(self._db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT 'system',
                    task_id TEXT,
                    approval_id TEXT,
                    tool_name TEXT,
                    action TEXT NOT NULL DEFAULT '',
                    outcome TEXT NOT NULL DEFAULT 'success',
                    reason TEXT,
                    severity TEXT,
                    detail TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.commit()

    def append(self, event: AuditEvent) -> AuditEvent:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO audit_events
                   (event_id, event_type, timestamp, actor, task_id, approval_id,
                    tool_name, action, outcome, reason, severity, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.actor,
                    event.task_id,
                    event.approval_id,
                    event.tool_name,
                    event.action,
                    event.outcome,
                    event.reason,
                    event.severity,
                    json.dumps(event.detail, ensure_ascii=False),
                ),
            )
            conn.commit()
        return event

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM audit_events WHERE event_id = ?", (event_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    def query_events(
        self,
        event_type: str | None = None,
        actor: str | None = None,
        task_id: str | None = None,
        approval_id: str | None = None,
        outcome: str | None = None,
        severity: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 100
        if limit > 500:
            limit = 500

        conditions: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if actor is not None:
            conditions.append("actor = ?")
            params.append(actor)
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if approval_id is not None:
            conditions.append("approval_id = ?")
            params.append(approval_id)
        if outcome is not None:
            conditions.append("outcome = ?")
            params.append(outcome)
        if severity is not None:
            conditions.append("severity = ?")
            params.append(severity)
        if start_time is not None:
            try:
                datetime.fromisoformat(start_time)
                conditions.append("timestamp >= ?")
                params.append(start_time)
            except (ValueError, TypeError):
                pass
        if end_time is not None:
            try:
                datetime.fromisoformat(end_time)
                conditions.append("timestamp <= ?")
                params.append(end_time)
            except (ValueError, TypeError):
                pass

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM audit_events WHERE {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if "detail" in d and isinstance(d["detail"], str):
            try:
                d["detail"] = json.loads(d["detail"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
