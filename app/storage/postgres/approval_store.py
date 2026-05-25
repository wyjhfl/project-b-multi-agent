from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import ApprovalRequest, RiskLevel
from app.storage.database import get_session_factory
from app.storage.models import ApprovalRequestRow


class PostgresApprovalStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

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
        with self._session_factory() as session:
            row = ApprovalRequestRow(
                approval_id=approval_id,
                task_id=task_id,
                tool_name=tool_name,
                action=action,
                risk_level=risk_level.value,
                impact_scope=impact_scope,
                agent_reason=agent_reason,
                status="pending",
                requested_at=now,
                payload_json=payload_json,
            )
            session.add(row)
            session.commit()
        return request

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.query(ApprovalRequestRow).filter_by(approval_id=approval_id).first()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_approvals(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            limit = 20
        if limit > 100:
            limit = 100
        with self._session_factory() as session:
            q = session.query(ApprovalRequestRow).order_by(ApprovalRequestRow.requested_at.desc())
            if status is not None:
                q = q.filter_by(status=status)
            rows = q.limit(limit).all()
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
        new_status = "approved" if approved else "rejected"
        with self._session_factory() as session:
            row = session.query(ApprovalRequestRow).filter_by(approval_id=approval_id, status="pending").first()
            if row is None:
                return None
            row.status = new_status
            row.decided_at = now
            row.decided_by = decided_by
            row.decision_reason = reason
            session.commit()
        return self.get_approval(approval_id)

    def update_payload(self, approval_id: str, payload_update: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_approval(approval_id)
        if current is None:
            return None
        existing_payload = current.get("payload") or {}
        existing_payload.update(payload_update)
        payload_json = json.dumps(existing_payload, ensure_ascii=False, default=str)
        with self._session_factory() as session:
            row = session.query(ApprovalRequestRow).filter_by(approval_id=approval_id).first()
            if row is None:
                return None
            row.payload_json = payload_json
            session.commit()
        return self.get_approval(approval_id)

    def _row_to_dict(self, row: ApprovalRequestRow) -> dict[str, Any]:
        d = {
            "approval_id": row.approval_id,
            "task_id": row.task_id,
            "tool_name": row.tool_name,
            "action": row.action,
            "risk_level": row.risk_level,
            "impact_scope": row.impact_scope,
            "agent_reason": row.agent_reason,
            "status": row.status,
            "requested_at": row.requested_at.isoformat() if row.requested_at else "",
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "decided_by": row.decided_by,
            "decision_reason": row.decision_reason,
        }
        if row.payload_json:
            try:
                d["payload"] = json.loads(row.payload_json)
            except (json.JSONDecodeError, TypeError):
                d["payload"] = None
        else:
            d["payload"] = None
        return d
