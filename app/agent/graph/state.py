from __future__ import annotations

from typing import Any, TypedDict

from app.models.schemas import AgentContext, TaskRun


class GraphRuntimeState(TypedDict, total=False):
    task_id: str
    query: str
    mode: str
    stage: str
    context: dict[str, Any] | None
    plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    response: dict[str, Any] | None
    error: str | None
    checkpoint_id: str | None
    checkpoint_status: str | None


class KeywordGraphState(TypedDict, total=False):
    """keyword 主链路 LangGraph 图状态

    AgentKernel.build_graph() 编译的 StateGraph 以此为状态 schema。
    task 为可变 TaskRun 对象，节点间按引用传递（_execute 中的
    status 变更对调用方直接可见），其余字段由各节点写入：
    - ctx: assemble_context 节点产出的 AgentContext
    - plan_result: plan 节点产出的规划结果
    - tool_record: execute 节点产出的工具调用记录（或拦截/审批 dict）
    - waiting_approval: execute 后 task 是否进入 waiting_approval
    - verified: verify 节点产出的校验结论
    - result: respond 节点产出的最终响应
    """

    task: TaskRun
    ctx: AgentContext | None
    plan_result: dict[str, Any] | None
    tool_record: Any
    verified: bool
    waiting_approval: bool
    result: dict[str, Any] | None
