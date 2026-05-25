from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas import AuditEvent
from app.storage.database import get_session_factory
from app.storage.models import AuditEventRow


class PostgresAuditStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def append(self, event: AuditEvent) -> AuditEvent:
        with self._session_factory() as session:
            row = AuditEventRow(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                actor=event.actor,
                task_id=event.task_id,
                approval_id=event.approval_id,
                tool_name=event.tool_name,
                action=event.action,
                outcome=event.outcome,
                reason=event.reason,
                severity=event.severity,
                detail=json.dumps(event.detail, ensure_ascii=False),
            )
            session.add(row)
            session.commit()
        return event

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.query(AuditEventRow).filter_by(event_id=event_id).first()
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
        with self._session_factory() as session:
            q = session.query(AuditEventRow)
            if event_type is not None:
                q = q.filter_by(event_type=event_type)
            if actor is not None:
                q = q.filter_by(actor=actor)
            if task_id is not None:
                q = q.filter_by(task_id=task_id)
            if approval_id is not None:
                q = q.filter_by(approval_id=approval_id)
            if outcome is not None:
                q = q.filter_by(outcome=outcome)
            if severity is not None:
                q = q.filter_by(severity=severity)
            if start_time is not None:
                try:
                    q = q.filter(AuditEventRow.timestamp >= datetime.fromisoformat(start_time))
                except (ValueError, TypeError):
                    pass
            if end_time is not None:
                try:
                    q = q.filter(AuditEventRow.timestamp <= datetime.fromisoformat(end_time))
                except (ValueError, TypeError):
                    pass
            rows = q.order_by(AuditEventRow.timestamp.desc()).limit(limit).all()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: AuditEventRow) -> dict[str, Any]:
        d = {
            "event_id": row.event_id,
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "actor": row.actor,
            "task_id": row.task_id,
            "approval_id": row.approval_id,
            "tool_name": row.tool_name,
            "action": row.action,
            "outcome": row.outcome,
            "reason": row.reason,
            "severity": row.severity,
        }
        if row.detail:
            try:
                d["detail"] = json.loads(row.detail) if isinstance(row.detail, str) else row.detail
            except (json.JSONDecodeError, TypeError):
                d["detail"] = row.detail
        else:
            d["detail"] = {}
        return d
