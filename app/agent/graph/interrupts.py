from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_tool_approval_interrupt_payload(
    *,
    task_id: str,
    checkpoint_id: str,
    tool_name: str,
    risk_level: str,
    permission_scope: str,
    policy_decision: dict[str, Any],
    agent_reason: str,
    arguments: dict[str, Any] | None = None,
    trace_context: dict[str, Any] | None = None,
    mode: str = "keyword",
    node: str = "execute",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "interrupt_type": "tool_approval",
        "task_id": task_id,
        "checkpoint_id": checkpoint_id,
        "node": node,
        "mode": mode,
        "tool_name": tool_name,
        "arguments": arguments or {},
        "risk_level": risk_level,
        "permission_scope": permission_scope,
        "policy_decision": policy_decision,
        "agent_reason": agent_reason,
        "trace_context": trace_context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
