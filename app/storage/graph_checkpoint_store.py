from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any

_JSON_COLUMNS = {"graph_state", "pending_interrupt", "resume_payload", "result_snapshot"}
_DATETIME_COLUMNS = {"resumed_at", "created_at", "updated_at", "expires_at", "locked_at"}


class SQLiteGraphCheckpointStore:
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
                CREATE TABLE IF NOT EXISTS graph_run_states (
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    approval_id TEXT,
                    graph_thread_id TEXT,
                    run_id TEXT,
                    status TEXT NOT NULL,
                    current_node TEXT,
                    graph_state TEXT NOT NULL,
                    pending_interrupt TEXT,
                    resume_payload TEXT,
                    result_snapshot TEXT,
                    consumed INTEGER NOT NULL DEFAULT 0,
                    resumed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    resume_attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_resume_error TEXT,
                    locked_by TEXT,
                    locked_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS ix_graph_run_states_task_id ON graph_run_states(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_graph_run_states_approval_id ON graph_run_states(approval_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_graph_run_states_status_expires_at ON graph_run_states(status, expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_graph_run_states_task_created_at ON graph_run_states(task_id, created_at)")
            conn.commit()

    def create_checkpoint(
        self,
        checkpoint_id: str,
        task_id: str,
        graph_state: dict[str, Any],
        approval_id: str | None = None,
        graph_thread_id: str | None = None,
        run_id: str | None = None,
        status: str = "running",
        current_node: str | None = None,
        pending_interrupt: dict[str, Any] | None = None,
        resume_payload: dict[str, Any] | None = None,
        result_snapshot: dict[str, Any] | None = None,
        consumed: bool = False,
        resumed_at: datetime | str | None = None,
        created_at: datetime | str | None = None,
        updated_at: datetime | str | None = None,
        expires_at: datetime | str | None = None,
        schema_version: int = 1,
        resume_attempt_count: int = 0,
        last_resume_error: str | None = None,
        locked_by: str | None = None,
        locked_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now()
        created = self._format_dt(created_at or now)
        updated = self._format_dt(updated_at or created_at or now)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO graph_run_states (
                    checkpoint_id, task_id, approval_id, graph_thread_id, run_id, status,
                    current_node, graph_state, pending_interrupt, resume_payload, result_snapshot,
                    consumed, resumed_at, created_at, updated_at, expires_at, schema_version,
                    resume_attempt_count, last_resume_error, locked_by, locked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    checkpoint_id,
                    task_id,
                    approval_id,
                    graph_thread_id,
                    run_id,
                    status,
                    current_node,
                    self._json_dumps(graph_state),
                    self._json_dumps(pending_interrupt),
                    self._json_dumps(resume_payload),
                    self._json_dumps(result_snapshot),
                    1 if consumed else 0,
                    self._format_dt(resumed_at),
                    created,
                    updated,
                    self._format_dt(expires_at),
                    schema_version,
                    resume_attempt_count,
                    last_resume_error,
                    locked_by,
                    self._format_dt(locked_at),
                ),
            )
            conn.commit()
        loaded = self.get_checkpoint(checkpoint_id)
        assert loaded is not None
        return loaded

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM graph_run_states WHERE checkpoint_id = ?", (checkpoint_id,))
            row = cur.fetchone()
        return self._row_to_dict(row) if row is not None else None

    def get_latest_for_task(self, task_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM graph_run_states WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            )
            row = cur.fetchone()
        return self._row_to_dict(row) if row is not None else None

    def mark_pending_interrupt(self, checkpoint_id: str, approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE graph_run_states
                   SET approval_id = ?, pending_interrupt = ?, status = 'interrupted', updated_at = ?
                   WHERE checkpoint_id = ?""",
                (approval_id, self._json_dumps(payload), now, checkpoint_id),
            )
            conn.commit()
        return self.get_checkpoint(checkpoint_id)

    def claim_for_resume(self, checkpoint_id: str, approval_id: str) -> dict[str, Any] | None:
        now = datetime.now()
        now_text = now.isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE graph_run_states
                   SET status = 'resuming', locked_at = ?, updated_at = ?, resume_attempt_count = resume_attempt_count + 1
                   WHERE checkpoint_id = ?
                     AND approval_id = ?
                     AND consumed = 0
                     AND status = 'interrupted'
                     AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)""",
                (now_text, now_text, checkpoint_id, approval_id, now_text),
            )
            changed = cur.rowcount
            conn.commit()
        if changed != 1:
            return None
        return self.get_checkpoint(checkpoint_id)

    def mark_resumed(
        self,
        checkpoint_id: str,
        resume_payload: dict[str, Any],
        result_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE graph_run_states
                   SET status = 'resumed', consumed = 1, resumed_at = ?, updated_at = ?,
                       resume_payload = ?, result_snapshot = ?
                   WHERE checkpoint_id = ?""",
                (now, now, self._json_dumps(resume_payload), self._json_dumps(result_snapshot), checkpoint_id),
            )
            conn.commit()
        return self.get_checkpoint(checkpoint_id)

    def mark_cancelled(self, checkpoint_id: str, reason: str) -> dict[str, Any] | None:
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE graph_run_states
                   SET status = 'cancelled', consumed = 1, updated_at = ?, last_resume_error = ?
                   WHERE checkpoint_id = ?""",
                (now, reason, checkpoint_id),
            )
            conn.commit()
        return self.get_checkpoint(checkpoint_id)

    def expire_old(self, now: datetime | str) -> int:
        now_text = self._format_dt(now) or datetime.now().isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE graph_run_states
                   SET status = 'expired', consumed = 1, updated_at = ?
                   WHERE consumed = 0
                     AND expires_at IS NOT NULL
                     AND expires_at != ''
                     AND expires_at <= ?""",
                (now_text, now_text),
            )
            changed = cur.rowcount
            conn.commit()
        return int(changed)

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for key in _JSON_COLUMNS:
            d[key] = self._json_loads(d.get(key))
        d["consumed"] = bool(d.get("consumed"))
        return d

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _json_loads(value: Any) -> Any:
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _format_dt(value: datetime | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
