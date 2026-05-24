from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.schemas import AgentContext, TaskRun


class ContextAssembler:
    """上下文组装器

    负责将 TaskRun、用户信息、可用工具列表、策略配置等组装为 AgentContext，
    供后续 Agent 内核消费。v0.1 使用 mock user 和 mock policy。
    """

    def assemble(
        self,
        task: TaskRun,
        user_info: dict[str, Any] | None = None,
        available_tools: list[str] | None = None,
        policies: dict[str, Any] | None = None,
        trace_context: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> AgentContext:
        metadata = {"source": "context_assembler"}
        if memory_context:
            metadata["memory_used"] = True
            metadata["memory_message_count"] = memory_context.get("message_count", 0)
        return AgentContext(
            task_id=task.task_id,
            user_query=task.query,
            user_info=user_info or self._mock_user(),
            available_tools=available_tools or [],
            policies=policies or self._mock_policy(),
            trace_context=trace_context or {},
            metadata=metadata,
            assembled_at=datetime.now(),
        )

    def _mock_user(self) -> dict[str, Any]:
        """v0.1 mock 用户信息"""
        return {
            "user_id": "mock_user_001",
            "role": "ops_analyst",
            "department": "运营部",
        }

    def _mock_policy(self) -> dict[str, Any]:
        """v0.1 mock 策略配置"""
        return {
            "allow_high_risk": False,
            "max_retries": 1,
            "timeout_seconds": 30,
        }
