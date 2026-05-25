from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.agent.graph.state import GraphRuntimeState
from app.agent.nodes.planner import KeywordPlanner
from app.models.schemas import RiskLevel, TaskRun


class GraphRuntimeAdapter:
    """Feature-flagged graph runtime smoke adapter.

    Phase 2.2 only supports a minimal low-risk keyword path. It writes durable
    graph checkpoints but deliberately does not implement LangGraph interrupt or
    approval resume.
    """

    STAGES = ["assemble_context", "plan", "execute", "verify", "respond"]

    def __init__(
        self,
        context_assembler: Any,
        gateway: Any,
        policy_engine: Any,
        checkpoint_store: Any,
        trace_recorder: Any | None = None,
        planner: KeywordPlanner | None = None,
    ) -> None:
        self._context_assembler = context_assembler
        self._gateway = gateway
        self._policy_engine = policy_engine
        self._checkpoint_store = checkpoint_store
        self._trace_recorder = trace_recorder
        self._planner = planner or KeywordPlanner()

    def run_keyword(self, task_id: str, query: str) -> dict[str, Any]:
        state: GraphRuntimeState = {
            "task_id": task_id,
            "query": query,
            "mode": "keyword",
            "stage": "created",
            "context": None,
            "plan": None,
            "execution_result": None,
            "response": None,
            "error": None,
            "checkpoint_id": None,
            "checkpoint_status": None,
        }

        try:
            task = TaskRun(task_id=task_id, query=query)
            ctx = self._context_assembler.assemble(
                task=task,
                available_tools=[spec.tool_name for spec in self._gateway.list_tools()],
            )
            state["stage"] = "assemble_context"
            state["context"] = ctx.model_dump(mode="json")
            self._checkpoint(state, "assemble_context", "running")

            plan = self._planner.plan(query)
            state["stage"] = "plan"
            state["plan"] = dict(plan)
            self._checkpoint(state, "plan", "running")

            tool_name = plan.get("tool_name")
            if not plan.get("matched") or not tool_name:
                response = {
                    "answer": "抱歉，我暂时无法识别您的问题。当前支持查询：今日 GMV、本月新增用户、订单数量、Top 商品、退款率。",
                    "tool_called": None,
                    "success": False,
                    "graph_runtime": True,
                }
                state["stage"] = "respond"
                state["response"] = response
                self._checkpoint(state, "respond", "completed")
                return response

            spec = self._gateway.get_tool(tool_name)
            if spec is None:
                response = {
                    "answer": f"工具 '{tool_name}' 未注册",
                    "tool_called": tool_name,
                    "success": False,
                    "graph_runtime": True,
                    "error": f"工具 '{tool_name}' 未注册",
                }
                state["stage"] = "respond"
                state["error"] = response["error"]
                state["response"] = response
                self._checkpoint(state, "respond", "failed")
                return response

            decision = self._policy_engine.evaluate(tool_name, risk_level=spec.risk_level)
            if spec.risk_level == RiskLevel.high or decision.get("requires_approval"):
                response = {
                    "answer": f"高风险工具 '{tool_name}' 需要人工审批；Phase 2.2 graph runtime 尚未实现 interrupt/resume。",
                    "tool_called": tool_name,
                    "success": False,
                    "requires_approval": True,
                    "not_supported": True,
                    "graph_runtime": True,
                    "graph_interrupt": False,
                    "risk_level": spec.risk_level.value,
                    "reason": decision.get("reason", "high risk not supported in graph runtime smoke path"),
                }
                state["stage"] = "execute"
                state["execution_result"] = response
                state["response"] = response
                self._checkpoint(state, "execute", "blocked")
                return response

            record = self._gateway.call(tool_name, task_id=task_id)
            execution_result = record.model_dump(mode="json")
            state["stage"] = "execute"
            state["execution_result"] = execution_result
            self._checkpoint(state, "execute", "running")

            verified = bool(record.success)
            state["stage"] = "verify"
            state["execution_result"] = {**execution_result, "verified": verified}
            self._checkpoint(state, "verify", "running")

            if verified:
                label = self._planner.get_label(tool_name)
                response = {
                    "answer": f"{label}查询结果：{record.result}",
                    "tool_called": tool_name,
                    "data": record.result,
                    "success": True,
                    "graph_runtime": True,
                }
            else:
                response = {
                    "answer": f"工具调用失败（{record.error}），请稍后重试。" if record.error else "工具调用失败，请稍后重试。",
                    "tool_called": tool_name,
                    "success": False,
                    "graph_runtime": True,
                    "error": record.error,
                }
            state["stage"] = "respond"
            state["response"] = response
            self._checkpoint(state, "respond", "completed" if verified else "failed")
            return response
        except Exception as exc:
            state["error"] = str(exc)
            state["response"] = {"success": False, "error": str(exc), "graph_runtime": True}
            self._checkpoint(state, state.get("stage", "error") or "error", "failed")
            return state["response"] or {"success": False, "error": str(exc), "graph_runtime": True}

    def _checkpoint(self, state: GraphRuntimeState, stage: str, status: str) -> str:
        checkpoint_id = f"graph-{state['task_id']}-{stage}-{uuid.uuid4().hex[:12]}"
        snapshot = dict(state)
        snapshot["stage"] = stage
        snapshot["checkpoint_id"] = checkpoint_id
        snapshot["checkpoint_status"] = status
        self._checkpoint_store.create_checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=state["task_id"],
            graph_state=snapshot,
            status=status,
            current_node=stage,
            graph_thread_id=f"graph-{state['task_id']}",
            run_id=str(snapshot.get("context", {}).get("trace_context", {}).get("run_id", "")) or None,
            created_at=datetime.now(),
        )
        state["checkpoint_id"] = checkpoint_id
        state["checkpoint_status"] = status
        if self._trace_recorder is not None:
            try:
                self._trace_recorder.record(
                    "graph_checkpoint_created",
                    task_id=state["task_id"],
                    detail={"checkpoint_id": checkpoint_id, "stage": stage, "status": status},
                )
            except Exception:
                pass
        return checkpoint_id
