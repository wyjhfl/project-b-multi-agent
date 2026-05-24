from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentRole = Literal["coordinator", "analyst", "executor", "reviewer"]


class AgentDecision(BaseModel):
    role: AgentRole = Field(..., description="角色名称")
    action: str = Field(..., description="执行的动作")
    reason: str = Field(default="", description="决策原因")
    confidence: float = Field(default=1.0, description="置信度 0-1")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class MultiAgentRunResult(BaseModel):
    mode: str = Field(default="multi_agent", description="执行模式")
    success: bool = Field(..., description="是否成功")
    requested_mode: str = Field(default="multi_agent", description="请求模式")
    executed_mode: str = Field(default="", description="实际执行模式")
    final_answer: str = Field(default="", description="最终答案")
    decisions: list[AgentDecision] = Field(default_factory=list, description="角色决策链")
    execution_result: dict[str, Any] | None = Field(default=None, description="执行结果")
    review_result: dict[str, Any] | None = Field(default=None, description="审查结果")
    fallback_chain: list[str] = Field(default_factory=list, description="fallback 链")
