from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import AuditEvent


class TraceRecorder:
    """追踪记录器

    负责记录 Agent 执行过程中的关键事件，形成完整的审计追踪链。
    v0.1 使用内存列表存储事件，v0.2+ 将对接持久化存储。
    支持的事件类型：task_started / context_assembled / plan_created /
    tool_called / task_completed / task_failed。
    """

    def record(
        self,
        event_type: str,
        task_id: str | None = None,
        actor: str = "system",
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """记录追踪事件

        Args:
            event_type: 事件类型
            task_id: 关联任务 ID
            actor: 执行者
            detail: 事件详情

        Returns:
            记录的 AuditEvent 实例
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            task_id=task_id,
            actor=actor,
            detail=detail or {},
            timestamp=datetime.now(),
        )
        self._events.append(event)
        return event

    def get_events(self, task_id: str | None = None, event_type: str | None = None) -> list[AuditEvent]:
        """获取追踪事件

        Args:
            task_id: 可选，按任务 ID 过滤
            event_type: 可选，按事件类型过滤

        Returns:
            事件列表
        """
        events = list(self._events)
        if task_id is not None:
            events = [e for e in events if e.task_id == task_id]
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        return events

    def clear(self) -> None:
        """清空所有追踪事件"""
        self._events.clear()

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
