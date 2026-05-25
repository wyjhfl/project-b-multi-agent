from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.schemas import TaskRun
from app.storage.database import get_session_factory
from app.storage.models import TaskRunRow


class PostgresTaskStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def save_task(self, task: TaskRun, mode: str | None = None) -> None:
        result_json = json.dumps(task.result, ensure_ascii=False, default=str) if task.result else None
        with self._session_factory() as session:
            existing = session.query(TaskRunRow).filter_by(task_id=task.task_id).first()
            if existing:
                existing.query = task.query
                existing.mode = mode or ""
                existing.status = task.status.value
                existing.result_json = result_json
                existing.error = task.error
                existing.updated_at = datetime.now()
            else:
                row = TaskRunRow(
                    task_id=task.task_id,
                    query=task.query,
                    mode=mode or "",
                    status=task.status.value,
                    result_json=result_json,
                    error=task.error,
                    created_at=task.created_at or datetime.now(),
                    updated_at=task.updated_at or datetime.now(),
                )
                session.add(row)
            session.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.query(TaskRunRow).filter_by(task_id=task_id).first()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 20
        if limit > 100:
            limit = 100
        with self._session_factory() as session:
            rows = session.query(TaskRunRow).order_by(TaskRunRow.created_at.desc()).limit(limit).all()
        return [self._row_to_dict(row) for row in rows]

    def update_task_status(self, task_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        existing = self.get_task(task_id)
        if existing is None:
            return None
        with self._session_factory() as session:
            row = session.query(TaskRunRow).filter_by(task_id=task_id).first()
            if row is None:
                return None
            row.status = status
            if result is not None:
                existing_result = existing.get("result") or {}
                existing_result.update(result)
                row.result_json = json.dumps(existing_result, ensure_ascii=False, default=str)
            row.updated_at = datetime.now()
            session.commit()
        return self.get_task(task_id)

    def _row_to_dict(self, row: TaskRunRow) -> dict[str, Any]:
        d = {
            "task_id": row.task_id,
            "query": row.query,
            "mode": row.mode,
            "status": row.status,
            "error": row.error,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }
        if row.result_json:
            try:
                d["result"] = json.loads(row.result_json)
            except (json.JSONDecodeError, TypeError):
                d["result"] = None
        else:
            d["result"] = None
        return d
