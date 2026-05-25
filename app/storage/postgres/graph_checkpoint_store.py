from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_

from app.storage.database import get_session_factory
from app.storage.models import GraphRunStateRow


class PostgresGraphCheckpointStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

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
        with self._session_factory() as session:
            existing = session.query(GraphRunStateRow).filter_by(checkpoint_id=checkpoint_id).first()
            row = existing or GraphRunStateRow(checkpoint_id=checkpoint_id)
            row.task_id = task_id
            row.approval_id = approval_id
            row.graph_thread_id = graph_thread_id
            row.run_id = run_id
            row.status = status
            row.current_node = current_node
            row.graph_state = graph_state
            row.pending_interrupt = pending_interrupt
            row.resume_payload = resume_payload
            row.result_snapshot = result_snapshot
            row.consumed = consumed
            row.resumed_at = self._parse_dt(resumed_at)
            row.created_at = self._parse_dt(created_at) or now
            row.updated_at = self._parse_dt(updated_at) or row.created_at or now
            row.expires_at = self._parse_dt(expires_at)
            row.schema_version = schema_version
            row.resume_attempt_count = resume_attempt_count
            row.last_resume_error = last_resume_error
            row.locked_by = locked_by
            row.locked_at = self._parse_dt(locked_at)
            if existing is None:
                session.add(row)
            session.commit()
        loaded = self.get_checkpoint(checkpoint_id)
        assert loaded is not None
        return loaded

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.query(GraphRunStateRow).filter_by(checkpoint_id=checkpoint_id).first()
        return self._row_to_dict(row) if row is not None else None

    def get_latest_for_task(self, task_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = (
                session.query(GraphRunStateRow)
                .filter_by(task_id=task_id)
                .order_by(GraphRunStateRow.created_at.desc())
                .first()
            )
        return self._row_to_dict(row) if row is not None else None

    def mark_pending_interrupt(self, checkpoint_id: str, approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now()
        with self._session_factory() as session:
            row = session.query(GraphRunStateRow).filter_by(checkpoint_id=checkpoint_id).first()
            if row is None:
                return None
            row.approval_id = approval_id
            row.pending_interrupt = payload
            row.status = "interrupted"
            row.updated_at = now
            session.commit()
        return self.get_checkpoint(checkpoint_id)

    def claim_for_resume(self, checkpoint_id: str, approval_id: str) -> dict[str, Any] | None:
        now = datetime.now()
        with self._session_factory() as session:
            changed = (
                session.query(GraphRunStateRow)
                .filter(
                    GraphRunStateRow.checkpoint_id == checkpoint_id,
                    GraphRunStateRow.approval_id == approval_id,
                    GraphRunStateRow.consumed.is_(False),
                    GraphRunStateRow.status == "interrupted",
                    or_(GraphRunStateRow.expires_at.is_(None), GraphRunStateRow.expires_at > now),
                )
                .update(
                    {
                        GraphRunStateRow.status: "resuming",
                        GraphRunStateRow.locked_at: now,
                        GraphRunStateRow.updated_at: now,
                        GraphRunStateRow.resume_attempt_count: GraphRunStateRow.resume_attempt_count + 1,
                    },
                    synchronize_session=False,
                )
            )
            session.commit()
        if changed != 1:
            return None
        return self.get_checkpoint(checkpoint_id)

    def mark_resumed(
        self,
        checkpoint_id: str,
        resume_payload: dict[str, Any],
        result_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now()
        with self._session_factory() as session:
            row = session.query(GraphRunStateRow).filter_by(checkpoint_id=checkpoint_id).first()
            if row is None:
                return None
            row.status = "resumed"
            row.consumed = True
            row.resumed_at = now
            row.updated_at = now
            row.resume_payload = resume_payload
            row.result_snapshot = result_snapshot
            session.commit()
        return self.get_checkpoint(checkpoint_id)

    def mark_cancelled(self, checkpoint_id: str, reason: str) -> dict[str, Any] | None:
        now = datetime.now()
        with self._session_factory() as session:
            row = session.query(GraphRunStateRow).filter_by(checkpoint_id=checkpoint_id).first()
            if row is None:
                return None
            row.status = "cancelled"
            row.consumed = True
            row.updated_at = now
            row.last_resume_error = reason
            session.commit()
        return self.get_checkpoint(checkpoint_id)

    def expire_old(self, now: datetime | str) -> int:
        now_dt = self._parse_dt(now) or datetime.now()
        with self._session_factory() as session:
            changed = (
                session.query(GraphRunStateRow)
                .filter(
                    GraphRunStateRow.consumed.is_(False),
                    GraphRunStateRow.expires_at.is_not(None),
                    GraphRunStateRow.expires_at <= now_dt,
                )
                .update(
                    {
                        GraphRunStateRow.status: "expired",
                        GraphRunStateRow.consumed: True,
                        GraphRunStateRow.updated_at: now_dt,
                    },
                    synchronize_session=False,
                )
            )
            session.commit()
        return int(changed)

    def _row_to_dict(self, row: GraphRunStateRow) -> dict[str, Any]:
        return {
            "checkpoint_id": row.checkpoint_id,
            "task_id": row.task_id,
            "approval_id": row.approval_id,
            "graph_thread_id": row.graph_thread_id,
            "run_id": row.run_id,
            "status": row.status,
            "current_node": row.current_node,
            "graph_state": row.graph_state,
            "pending_interrupt": row.pending_interrupt,
            "resume_payload": row.resume_payload,
            "result_snapshot": row.result_snapshot,
            "consumed": bool(row.consumed),
            "resumed_at": row.resumed_at.isoformat() if row.resumed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "schema_version": row.schema_version,
            "resume_attempt_count": row.resume_attempt_count,
            "last_resume_error": row.last_resume_error,
            "locked_by": row.locked_by,
            "locked_at": row.locked_at.isoformat() if row.locked_at else None,
        }

    @staticmethod
    def _parse_dt(value: datetime | str | None) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
