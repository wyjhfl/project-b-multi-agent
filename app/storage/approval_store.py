from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from typing import Any

from app.models.schemas import ApprovalRequest, RiskLevel


class SQLiteApprovalStore:
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
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    tool_name TEXT,
                    action TEXT,
                    risk_level TEXT,
                    impact_scope TEXT,
                    agent_reason TEXT,
                    status TEXT,
                    requested_at TEXT,
                    decided_at TEXT,
                    decided_by TEXT,
                    decision_reason TEXT,
                    payload_json TEXT
                )
            """)
            conn.commit()

    def create_approval(
        self,
        task_id: str,
        tool_name: str,
        action: str,
        risk_level: RiskLevel = RiskLevel.high,
        impact_scope: str = "",
        agent_reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        request = ApprovalRequest(
            approval_id=approval_id,
            task_id=task_id,
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            impact_scope=impact_scope,
            agent_reason=agent_reason,
            status="pending",
            requested_at=now,
        )
        payload_json = json.dumps(payload, ensure_ascii=False, default=str) if payload else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO approvals
                   (approval_id, task_id, tool_name, action, risk_level, impact_scope,
                    agent_reason, status, requested_at, decided_at, decided_by, decision_reason, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval_id,
                    task_id,
                    tool_name,
                    action,
                    risk_level.value,
                    impact_scope,
                    agent_reason,
                    "pending",
                    now.isoformat(),
                    None,
                    None,
                    None,
                    payload_json,
                ),
            )
            conn.commit()
        return request

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_approvals(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 20
        if limit > 100:
            limit = 100
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if status is not None:
                cur.execute(
                    "SELECT * FROM approvals WHERE status = ? ORDER BY requested_at DESC LIMIT ?",
                    (status, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM approvals ORDER BY requested_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def decide_approval(
        self,
        approval_id: str,
        approved: bool,
        decided_by: str = "admin",
        reason: str = "",
    ) -> dict[str, Any] | None:
        current = self.get_approval(approval_id)
        if current is None:
            return None

        if current.get("status") != "pending":
            current["already_decided"] = True
            current["decision_error"] = f"审批已决策，当前状态为 {current['status']}"
            return current

        now = datetime.now()
        status = "approved" if approved else "rejected"
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE approvals
                   SET status = ?, decided_at = ?, decided_by = ?, decision_reason = ?
                   WHERE approval_id = ? AND status = 'pending'""",
                (status, now.isoformat(), decided_by, reason, approval_id),
            )
            conn.commit()
        return self.get_approval(approval_id)

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("payload_json"):
            try:
                d["payload"] = json.loads(d["payload_json"])
            except (json.JSONDecodeError, TypeError):
                d["payload"] = None
        else:
            d["payload"] = None
        del d["payload_json"]
        return d

    def update_payload(self, approval_id: str, payload_update: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_approval(approval_id)
        if current is None:
            return None

        existing_payload = current.get("payload") or {}
        existing_payload.update(payload_update)
        payload_json = json.dumps(existing_payload, ensure_ascii=False, default=str)

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "UPDATE approvals SET payload_json = ? WHERE approval_id = ?",
                (payload_json, approval_id),
            )
            conn.commit()
        return self.get_approval(approval_id)
