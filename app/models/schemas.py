from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    created = "created"
    pending = "pending"
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskRun(BaseModel):
    task_id: str = Field(..., description="任务唯一标识")
    query: str = Field(..., description="用户原始查询")
    status: TaskStatus = Field(default=TaskStatus.created, description="任务状态")
    result: Any | None = Field(default=None, description="任务结果")
    error: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class AgentContext(BaseModel):
    task_id: str = Field(..., description="关联任务 ID")
    user_query: str = Field(..., description="用户查询")
    user_info: dict[str, Any] = Field(default_factory=dict, description="用户信息")
    available_tools: list[str] = Field(default_factory=list, description="可用工具列表")
    policies: dict[str, Any] = Field(default_factory=dict, description="策略配置")
    trace_context: dict[str, Any] = Field(default_factory=dict, description="追踪上下文")
    metadata: dict[str, Any] = Field(default_factory=dict, description="上下文元数据")
    assembled_at: datetime | None = Field(default=None, description="上下文组装时间")


class ToolSpec(BaseModel):
    tool_name: str = Field(..., description="工具名称")
    description: str = Field(default="", description="工具描述")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="输入参数 JSON Schema")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="输出参数 JSON Schema")
    risk_level: RiskLevel = Field(default=RiskLevel.low, description="风险等级")
    permission_scope: str = Field(default="read", description="权限范围")
    timeout_seconds: float = Field(default=30.0, description="超时时间（秒）")
    retry_policy: dict[str, Any] = Field(default_factory=dict, description="重试策略")
    is_local: bool = Field(default=True, description="是否为本地工具")
    source: str = Field(default="local", description="工具来源: local 或 mcp")
    server_name: str | None = Field(default=None, description="MCP Server 名称")
    mcp_tool_name: str | None = Field(default=None, description="MCP 工具原始名称")


class ToolCallStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ToolCallRecord(BaseModel):
    call_id: str = Field(..., description="调用唯一标识")
    tool_name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    result: Any | None = Field(default=None, description="调用结果")
    status: ToolCallStatus = Field(default=ToolCallStatus.pending, description="调用状态")
    success: bool = Field(default=True, description="是否成功")
    latency_ms: float = Field(default=0.0, description="调用耗时（毫秒）")
    retry_count: int = Field(default=0, description="重试次数")
    error: str | None = Field(default=None, description="错误信息")
    called_at: datetime = Field(default_factory=datetime.now, description="调用时间")


class ApprovalRequest(BaseModel):
    approval_id: str = Field(..., description="审批请求 ID")
    task_id: str = Field(..., description="关联任务 ID")
    tool_name: str = Field(default="", description="关联工具名称")
    action: str = Field(..., description="待审批动作")
    risk_level: RiskLevel = Field(default=RiskLevel.high, description="风险等级")
    impact_scope: str = Field(default="", description="影响范围")
    agent_reason: str = Field(default="", description="Agent 申请原因")
    status: Literal["pending", "approved", "rejected", "expired"] = Field(default="pending", description="审批状态")
    reason: str = Field(default="", description="审批原因")
    requested_at: datetime = Field(default_factory=datetime.now, description="请求时间")
    decided_at: datetime | None = Field(default=None, description="决策时间")
    decided_by: str | None = Field(default=None, description="决策人")
    decision_reason: str | None = Field(default=None, description="决策原因")
    approved: bool | None = Field(default=None, description="审批结果")


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}", description="事件 ID")
    event_type: str = Field(..., description="事件类型")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="事件时间（UTC）")
    actor: str = Field(default="system", description="执行者")
    task_id: str | None = Field(default=None, description="关联任务 ID")
    approval_id: str | None = Field(default=None, description="关联审批 ID")
    tool_name: str | None = Field(default=None, description="关联工具名称")
    action: str = Field(default="", description="动作描述")
    outcome: str = Field(default="success", description="结果: success/blocked/failed/approved/rejected")
    reason: str | None = Field(default=None, description="原因")
    severity: str | None = Field(default=None, description="严重级别: info/warn/high/critical")
    detail: dict[str, Any] = Field(default_factory=dict, description="事件详情")


class EvalCase(BaseModel):
    case_id: str = Field(..., description="评估用例 ID")
    input_query: str = Field(..., description="输入查询")
    expected_output: str = Field(default="", description="期望输出")
    actual_output: str | None = Field(default=None, description="实际输出")
    score: float | None = Field(default=None, description="评分")
    passed: bool | None = Field(default=None, description="是否通过")
