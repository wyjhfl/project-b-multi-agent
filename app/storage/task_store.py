from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any

from app.models.schemas import TaskRun


class SQLiteTaskStore:
    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from app.core.config import settings
            db_path = getattr(settings, "runtime_db_path", "data/db/runtime.sqlite")
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        dir_name = os.path.dirname(self._db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    query TEXT,
                    mode TEXT,
                    status TEXT,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()

    def save_task(self, task: TaskRun, mode: str | None = None) -> None:
        result_json = json.dumps(task.result, ensure_ascii=False, default=str) if task.result else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks (task_id, query, mode, status, result_json, error, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.task_id,
                    task.query,
                    mode or "",
                    task.status.value,
                    result_json,
                    task.error,
                    task.created_at.isoformat() if task.created_at else "",
                    task.updated_at.isoformat() if task.updated_at else "",
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 20
        if limit > 100:
            limit = 100
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("result_json"):
            try:
                d["result"] = json.loads(d["result_json"])
            except (json.JSONDecodeError, TypeError):
                d["result"] = None
        else:
            d["result"] = None
        del d["result_json"]
        return d

    def update_task_status(self, task_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        existing = self.get_task(task_id)
        if existing is None:
            return None

        if result is not None:
            existing_result = existing.get("result") or {}
            existing_result.update(result)
            result_json = json.dumps(existing_result, ensure_ascii=False, default=str)
        else:
            result_json = json.dumps(existing.get("result"), ensure_ascii=False, default=str) if existing.get("result") else None

        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE tasks SET status = ?, result_json = ?, updated_at = ?
                   WHERE task_id = ?""",
                (status, result_json, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)
