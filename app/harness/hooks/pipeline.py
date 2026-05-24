from __future__ import annotations

from typing import Any, Callable


HookFn = Callable[[dict[str, Any]], dict[str, Any]]


class HookStage:
    before_task = "before_task"
    before_tool_call = "before_tool_call"
    after_tool_call = "after_tool_call"
    after_task = "after_task"
    on_error = "on_error"


class HookPipeline:
    """Hook 管线

    支持在 Agent 执行流程的关键节点插入自定义钩子函数。
    v0.1 支持 5 个 stage：before_task / before_tool_call / after_tool_call / after_task / on_error。
    每个 stage 支持注册多个 hook，按注册顺序依次执行。
    hook 异常不会被静默吞掉，而是在 payload 中增加 hook_errors 列表。
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = {
            HookStage.before_task: [],
            HookStage.before_tool_call: [],
            HookStage.after_tool_call: [],
            HookStage.after_task: [],
            HookStage.on_error: [],
        }

    def register(self, stage: str, hook: HookFn) -> None:
        """注册钩子到指定 stage

        Args:
            stage: 钩子阶段
            hook: 钩子函数，接收 payload 字典，返回修改后的 payload
        """
        if stage not in self._hooks:
            self._hooks[stage] = []
        self._hooks[stage].append(hook)

    def run(self, stage: str, payload: dict[str, Any]) -> dict[str, Any]:
        """执行指定 stage 的所有钩子

        Args:
            stage: 钩子阶段
            payload: 传递给钩子的负载数据

        Returns:
            经过所有钩子处理后的 payload，如有 hook 异常则增加 hook_errors 字段
        """
        hooks = self._hooks.get(stage, [])
        hook_errors: list[dict[str, str]] = []
        for hook in hooks:
            try:
                payload = hook(payload)
            except Exception as exc:
                hook_errors.append({
                    "stage": stage,
                    "error": str(exc),
                })
        if hook_errors:
            existing = payload.get("hook_errors", [])
            existing.extend(hook_errors)
            payload["hook_errors"] = existing
        return payload
