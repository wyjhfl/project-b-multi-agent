from __future__ import annotations

import logging
from typing import Any

from app.models.schemas import AuditEvent
from app.storage.audit_store import SQLiteAuditStore

logger = logging.getLogger(__name__)


class AuditRecorder:
    def __init__(self, store: SQLiteAuditStore) -> None:
        self._store = store

    def record(
        self,
        event_type: str,
        actor: str = "system",
        task_id: str | None = None,
        approval_id: str | None = None,
        tool_name: str | None = None,
        action: str = "",
        outcome: str = "success",
        reason: str | None = None,
        severity: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            task_id=task_id,
            approval_id=approval_id,
            tool_name=tool_name,
            action=action,
            outcome=outcome,
            reason=reason,
            severity=severity,
            detail=detail or {},
        )
        try:
            self._store.append(event)
            return event
        except Exception as exc:
            logger.warning("AuditRecorder 写入失败: %s", exc)
            return None
