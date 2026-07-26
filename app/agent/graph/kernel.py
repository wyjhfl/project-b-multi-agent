from __future__ import annotations

from typing import Any

from app.agent.graph.state import KeywordGraphState
from app.agent.nodes.planner import KeywordPlanner
from app.core.config import settings
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline, HookStage
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import AgentContext, TaskRun, TaskStatus


class AgentKernel:
    """Agent 内核

    keyword 主链路经 LangGraph StateGraph 执行：
        assemble_context → plan → execute →（条件边）→ verify → respond
    图在 run() 首次调用时懒构建；langgraph 意外不可用时降级为
    _run_sequential 顺序调用，trace 的 task_started 事件以
    engine=langgraph|sequential 注明实际执行引擎。

    nl2sql / multitool / multi_agent 模式为管道式执行（非图执行）；
    checkpoint / HITL 恢复由自研 GraphRuntimeAdapter 状态机负责
    （非 LangGraph 原生 checkpointer）。

    规划器由 settings.planner_mode 选择：keyword（默认）使用 KeywordPlanner，
    llm 使用 LLMToolPlanner（LLM function calling 选工具，失败降级
    KeywordPlanner）；策略评估与高风险审批在 _execute 内，与规划器无关。

    v0.3.3 mode 支持：
        - keyword: LangGraph 图执行工具路径
        - nl2sql: v0.2 SQL Pipeline
        - multitool: v0.3.2 多工具串联
        - auto: NL2SQL → multitool → keyword fallback
    v0.3.3 auto 可观测：
        - requested_mode / executed_mode / fallback_chain
    """

    GRAPH_NODES = [
        "assemble_context",
        "plan",
        "execute",
        "verify",
        "respond",
    ]

    def __init__(
        self,
        context_assembler: ContextAssembler,
        tool_gateway: ToolGateway,
        hook_pipeline: HookPipeline,
        policy_engine: PolicyEngine,
        trace_recorder: TraceRecorder,
        planner: KeywordPlanner | None = None,
        nl2sql_pipeline: Any | None = None,
        multitool_pipeline: Any | None = None,
        multi_agent_orchestrator: Any | None = None,
        approval_store: Any | None = None,
        graph_runtime_adapter: Any | None = None,
    ) -> None:
        self._context_assembler = context_assembler
        self._tool_gateway = tool_gateway
        self._hook_pipeline = hook_pipeline
        self._policy_engine = policy_engine
        self._trace_recorder = trace_recorder
        self._planner = planner or KeywordPlanner()
        self._nl2sql_pipeline = nl2sql_pipeline
        self._multitool_pipeline = multitool_pipeline
        self._multi_agent_orchestrator = multi_agent_orchestrator
        self._approval_store = approval_store
        self._graph_runtime_adapter = graph_runtime_adapter
        self._metrics_recorder: Any | None = None
        self._memory: Any | None = None
        self._self_check_engine: Any | None = None
        self._graph: Any | None = None
        self._llm_planner: Any | None = None

    def set_metrics_recorder(self, recorder: Any) -> None:
        self._metrics_recorder = recorder

    def set_memory(self, memory: Any) -> None:
        self._memory = memory

    def set_self_check_engine(self, engine: Any) -> None:
        self._self_check_engine = engine

    def build_graph(self) -> None:
        """构建 keyword 主链路的 LangGraph StateGraph

        各节点仅包装既有私有方法（_assemble_context/_plan/_execute/
        _verify/_respond），不复制业务逻辑；execute 后的条件边在 task
        进入 waiting_approval 时跳过 verify 直接 respond，与
        _run_sequential 的顺序调用行为保持一致。构建失败时 _graph
        置为 None，run() 会降级到顺序执行。
        """
        try:
            from langgraph.graph import END, START, StateGraph

            def _assemble_context_node(state: KeywordGraphState) -> dict:
                return {"ctx": self._assemble_context(state["task"])}

            def _plan_node(state: KeywordGraphState) -> dict:
                return {"plan_result": self._plan(state["ctx"])}

            def _execute_node(state: KeywordGraphState) -> dict:
                task = state["task"]
                tool_record = self._execute(task, state["plan_result"])
                return {
                    "tool_record": tool_record,
                    "waiting_approval": task.status == TaskStatus.waiting_approval,
                }

            def _verify_node(state: KeywordGraphState) -> dict:
                return {"verified": self._verify(state.get("tool_record"))}

            def _respond_node(state: KeywordGraphState) -> dict:
                verified = False if state.get("waiting_approval") else bool(state.get("verified"))
                return {"result": self._respond(state["plan_result"], state.get("tool_record"), verified)}

            def _route_after_execute(state: KeywordGraphState) -> str:
                return "respond" if state.get("waiting_approval") else "verify"

            graph = StateGraph(KeywordGraphState)
            graph.add_node("assemble_context", _assemble_context_node)
            graph.add_node("plan", _plan_node)
            graph.add_node("execute", _execute_node)
            graph.add_node("verify", _verify_node)
            graph.add_node("respond", _respond_node)

            graph.add_edge(START, "assemble_context")
            graph.add_edge("assemble_context", "plan")
            graph.add_edge("plan", "execute")
            graph.add_conditional_edges("execute", _route_after_execute, {"verify": "verify", "respond": "respond"})
            graph.add_edge("verify", "respond")
            graph.add_edge("respond", END)

            self._graph = graph.compile()
        except Exception as exc:
            self._graph = None
            self._graph_error = str(exc)

    def get_graph_summary(self) -> dict:
        if self._graph is None:
            return {
                "implemented": False,
                "nodes": [],
                "edges": [],
                "error": getattr(self, "_graph_error", "build_graph() not called"),
            }
        try:
            g = self._graph.get_graph()
            nodes = [n for n in g.nodes if n not in ("__start__", "__end__")]
            edges = []
            for edge in g.edges:
                src = edge[0] if len(edge) > 0 else ""
                tgt = edge[1] if len(edge) > 1 else ""
                if src == "__start__":
                    src = "START"
                if tgt == "__end__":
                    tgt = "END"
                edges.append(f"{src} → {tgt}")
            return {
                "implemented": True,
                "nodes": nodes,
                "edges": edges,
            }
        except Exception as exc:
            return {
                "implemented": True,
                "nodes": list(self.GRAPH_NODES),
                "edges": [],
                "error": str(exc),
            }

    async def run(self, task: TaskRun, session_id: str | None = None) -> TaskRun:
        """执行 keyword 主链路

        首次调用时懒构建 LangGraph 图，主链路经 self._graph.invoke()
        执行；langgraph 不可用（构建失败）时降级为 _run_sequential
        顺序调用。hooks / trace / memory / metrics / self_check 的
        时序与图执行无关，保持在 run() 内。
        """
        task.status = TaskStatus.running
        task.updated_at = self._now()

        sid = session_id or task.task_id
        self._memory_add(sid, "user", task.query)

        if self._graph is None:
            self.build_graph()
        engine = "langgraph" if self._graph is not None else "sequential"

        try:
            self._trace_recorder.record("task_started", task_id=task.task_id, detail={"query": task.query, "engine": engine})

            hook_payload = self._hook_pipeline.run(HookStage.before_task, {"task_id": task.task_id, "query": task.query})
            self._check_hook_errors(task.task_id, hook_payload)

            if engine == "langgraph":
                final_state = self._graph.invoke({"task": task})
                result = final_state["result"]
            else:
                result = self._run_sequential(task)

            if task.status == TaskStatus.waiting_approval:
                task.result = result
                task.updated_at = self._now()
                return task

            task.result = result

            hook_payload = self._hook_pipeline.run(HookStage.after_task, {"task_id": task.task_id, "result": result})
            self._check_hook_errors(task.task_id, hook_payload)

            task.status = TaskStatus.completed
            self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(result)[:200]})

            self._memory_add(sid, "assistant", str(result.get("answer", ""))[:200])

        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = str(exc)
            self._hook_pipeline.run(HookStage.on_error, {"task_id": task.task_id, "error": str(exc)})
            self._trace_recorder.record("task_failed", task_id=task.task_id, detail={"error": str(exc)})

        self._record_task_metrics(task, "keyword")
        self._run_self_check(task)
        task.updated_at = self._now()
        return task

    def _run_sequential(self, task: TaskRun) -> dict[str, Any]:
        """keyword 主链路的顺序调用 fallback

        与 build_graph() 编译的图节点等价：assemble_context → plan →
        execute → verify → respond，task 进入 waiting_approval 时跳过
        verify。仅在 langgraph 不可用时由 run() 使用。
        """
        ctx = self._assemble_context(task)
        plan_result = self._plan(ctx)
        tool_record = self._execute(task, plan_result)

        if task.status == TaskStatus.waiting_approval:
            return self._respond(plan_result, tool_record, False)

        verified = self._verify(tool_record)
        return self._respond(plan_result, tool_record, verified)

    async def run_with_options(
        self,
        task: TaskRun,
        mode: str = "keyword",
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
        session_id: str | None = None,
    ) -> TaskRun:
        sid = session_id or task.task_id
        self._memory_add(sid, "user", task.query)

        if mode == "keyword":
            try:
                from app.core.config import settings
                graph_enabled = bool(getattr(settings, "graph_runtime_enabled", False))
            except Exception:
                graph_enabled = False
            if graph_enabled and self._graph_runtime_adapter is not None:
                result_payload = self._graph_runtime_adapter.run_keyword(task.task_id, task.query)
                task.result = result_payload
                if result_payload.get("requires_approval"):
                    task.status = TaskStatus.waiting_approval if result_payload.get("approval_id") else TaskStatus.failed
                elif result_payload.get("success"):
                    task.status = TaskStatus.completed
                else:
                    task.status = TaskStatus.failed
                task.updated_at = self._now()
                self._record_task_metrics(task, "keyword")
                self._memory_add(sid, "assistant", str(result_payload.get("answer", ""))[:200])
                self._run_self_check(task)
                return task

        if mode == "nl2sql":
            result = await self._run_nl2sql(task, generator, provider, fallback_to_mock)
            self._record_task_metrics(result, "nl2sql")
            self._memory_add(sid, "assistant", str(result.result.get("answer", ""))[:200] if result.result else "")
            self._run_self_check(result)
            return result
        elif mode == "multitool":
            result = await self._run_multitool(task)
            self._record_task_metrics(result, "multitool")
            self._memory_add(sid, "assistant", str(result.result.get("answer", ""))[:200] if result.result else "")
            self._run_self_check(result)
            return result
        elif mode == "multi_agent":
            result = await self._run_multi_agent(task, generator, provider, fallback_to_mock)
            self._record_task_metrics(result, "multi_agent")
            self._memory_add(sid, "assistant", str(result.result.get("answer", ""))[:200] if result.result else "")
            self._run_self_check(result)
            return result
        elif mode == "auto":
            result = await self._run_auto(task, generator, provider, fallback_to_mock)
            self._record_task_metrics(result, "auto")
            self._memory_add(sid, "assistant", str(result.result.get("answer", ""))[:200] if result.result else "")
            self._run_self_check(result)
            return result
        else:
            return await self.run(task, session_id=session_id)

    async def _run_nl2sql(
        self,
        task: TaskRun,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
    ) -> TaskRun:
        task.status = TaskStatus.running
        task.updated_at = self._now()

        try:
            self._trace_recorder.record("task_started", task_id=task.task_id, detail={"query": task.query, "mode": "nl2sql"})
            self._trace_recorder.record("nl2sql_started", task_id=task.task_id, detail={"generator": generator, "provider": provider})

            if self._nl2sql_pipeline is None:
                from app.services.nl2sql_pipeline import NL2SQLPipeline
                self._nl2sql_pipeline = NL2SQLPipeline()

            result = self._nl2sql_pipeline.run(
                query=task.query,
                generator=generator,
                provider=provider,
                fallback_to_mock=fallback_to_mock,
            )
            task.result = result

            self._trace_recorder.record("nl2sql_completed", task_id=task.task_id, detail={
                "success": result["success"],
                "generator_used": result["generator_used"],
                "sql": result.get("sql", "")[:100],
            })

            task.status = TaskStatus.completed
            self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(result)[:200]})

        except Exception as exc:
            task.status = TaskStatus.completed
            task.result = {
                "mode": "nl2sql",
                "success": False,
                "answer": f"NL2SQL 执行异常: {exc}",
            }
            self._trace_recorder.record("nl2sql_failed", task_id=task.task_id, detail={"error": str(exc)})

        task.updated_at = self._now()
        return task

    async def _run_multitool(self, task: TaskRun) -> TaskRun:
        task.status = TaskStatus.running
        task.updated_at = self._now()

        try:
            self._trace_recorder.record("task_started", task_id=task.task_id, detail={"query": task.query, "mode": "multitool"})
            self._trace_recorder.record("multitool_started", task_id=task.task_id, detail={"query": task.query})

            if self._multitool_pipeline is None:
                from app.services.multitool_pipeline import MultiToolPipeline
                self._multitool_pipeline = MultiToolPipeline(self._tool_gateway, policy_engine=self._policy_engine, trace_recorder=self._trace_recorder)

            result = self._multitool_pipeline.run(query=task.query, task_id=task.task_id)
            task.result = result

            if result.get("requires_approval"):
                task.status = TaskStatus.waiting_approval
                self._trace_recorder.record("multitool_waiting_approval", task_id=task.task_id, detail={
                    "approval_id": result.get("approval_id"),
                    "failed_step": result.get("failed_step"),
                })
                task.updated_at = self._now()
                return task

            if result["success"]:
                self._trace_recorder.record("multitool_completed", task_id=task.task_id, detail={"intent": result.get("intent", ""), "steps": len(result.get("tool_calls", []))})
            else:
                self._trace_recorder.record("multitool_failed", task_id=task.task_id, detail={"intent": result.get("intent", ""), "reason": result.get("answer", "")})

            task.status = TaskStatus.completed
            self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(result)[:200]})

        except Exception as exc:
            task.status = TaskStatus.completed
            task.result = {
                "mode": "multitool",
                "success": False,
                "answer": f"多工具执行异常: {exc}",
            }
            self._trace_recorder.record("multitool_failed", task_id=task.task_id, detail={"error": str(exc)})

        task.updated_at = self._now()
        return task

    async def _run_multi_agent(
        self,
        task: TaskRun,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
    ) -> TaskRun:
        task.status = TaskStatus.running
        task.updated_at = self._now()

        try:
            self._trace_recorder.record("task_started", task_id=task.task_id, detail={"query": task.query, "mode": "multi_agent"})

            if self._multi_agent_orchestrator is None:
                from app.agent.multi_agent.executor import ExecutorAgent
                from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
                executor = ExecutorAgent(
                    nl2sql_pipeline=self._nl2sql_pipeline,
                    multitool_pipeline=self._multitool_pipeline,
                    tool_gateway=self._tool_gateway,
                    policy_engine=self._policy_engine,
                    planner=self._planner,
                )
                self._multi_agent_orchestrator = MultiAgentOrchestrator(executor, trace_recorder=self._trace_recorder)

            ma_result = self._multi_agent_orchestrator.run(
                query=task.query,
                task_id=task.task_id,
                generator=generator,
                provider=provider,
                fallback_to_mock=fallback_to_mock,
            )
            task.result = ma_result.model_dump()
            task.status = TaskStatus.completed
            self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(ma_result.final_answer)[:200]})

        except Exception as exc:
            task.status = TaskStatus.completed
            task.result = {
                "mode": "multi_agent",
                "success": False,
                "final_answer": f"多 Agent 执行异常: {exc}",
            }
            self._trace_recorder.record("multi_agent_failed", task_id=task.task_id, detail={"error": str(exc)})

        task.updated_at = self._now()
        return task

    async def _run_auto(
        self,
        task: TaskRun,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
    ) -> TaskRun:
        task.status = TaskStatus.running
        task.updated_at = self._now()

        fallback_chain: list[str] = ["nl2sql"]

        try:
            self._trace_recorder.record("task_started", task_id=task.task_id, detail={"query": task.query, "mode": "auto"})
            self._trace_recorder.record("nl2sql_started", task_id=task.task_id, detail={"generator": generator, "provider": provider})

            if self._nl2sql_pipeline is None:
                from app.services.nl2sql_pipeline import NL2SQLPipeline
                self._nl2sql_pipeline = NL2SQLPipeline()

            result = self._nl2sql_pipeline.run(
                query=task.query,
                generator=generator,
                provider=provider,
                fallback_to_mock=fallback_to_mock,
            )

            if result["success"]:
                result["requested_mode"] = "auto"
                result["executed_mode"] = "nl2sql"
                result["fallback_chain"] = fallback_chain
                task.result = result
                self._trace_recorder.record("nl2sql_completed", task_id=task.task_id, detail={"success": True})
                task.status = TaskStatus.completed
                self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(result)[:200]})
                task.updated_at = self._now()
                return task

            self._trace_recorder.record("nl2sql_completed", task_id=task.task_id, detail={"success": False, "reason": result.get("guard_reason", "")})

            fallback_chain.append("multitool")

            if self._multitool_pipeline is None:
                from app.services.multitool_pipeline import MultiToolPipeline
                self._multitool_pipeline = MultiToolPipeline(self._tool_gateway, policy_engine=self._policy_engine, trace_recorder=self._trace_recorder)

            self._trace_recorder.record("auto_fallback_multitool", task_id=task.task_id, detail={"reason": "nl2sql failed"})
            self._trace_recorder.record("multitool_started", task_id=task.task_id, detail={"query": task.query})

            mt_result = self._multitool_pipeline.run(query=task.query, task_id=task.task_id)

            if mt_result["success"]:
                mt_result["requested_mode"] = "auto"
                mt_result["executed_mode"] = "multitool"
                mt_result["fallback_chain"] = fallback_chain
                mt_result["auto_fallback"] = True
                mt_result["auto_fallback_reason"] = "nl2sql 失败，回退到 multitool 模式"
                task.result = mt_result
                self._trace_recorder.record("multitool_completed", task_id=task.task_id, detail={"intent": mt_result.get("intent", "")})
                task.status = TaskStatus.completed
                self._trace_recorder.record("task_completed", task_id=task.task_id, detail={"result_summary": str(mt_result)[:200]})
                task.updated_at = self._now()
                return task

            self._trace_recorder.record("multitool_failed", task_id=task.task_id, detail={"reason": mt_result.get("answer", "")})

            fallback_chain.append("keyword")
            self._trace_recorder.record("auto_fallback_keyword", task_id=task.task_id, detail={"reason": "multitool failed"})

            task = await self.run(task)
            if task.result is None:
                task.result = {}
            task.result["requested_mode"] = "auto"
            task.result["executed_mode"] = "keyword"
            task.result["fallback_chain"] = fallback_chain
            task.result["auto_fallback"] = True
            task.result["auto_fallback_reason"] = "nl2sql 和 multitool 均失败，回退到 keyword 模式"

        except Exception as exc:
            self._trace_recorder.record("nl2sql_failed", task_id=task.task_id, detail={"error": str(exc)})

            fallback_chain.append("keyword")
            self._trace_recorder.record("auto_fallback_keyword", task_id=task.task_id, detail={"reason": str(exc)})

            task = await self.run(task)
            if task.result is None:
                task.result = {}
            task.result["requested_mode"] = "auto"
            task.result["executed_mode"] = "keyword"
            task.result["fallback_chain"] = fallback_chain
            task.result["auto_fallback"] = True
            task.result["auto_fallback_reason"] = f"nl2sql 异常: {exc}"

        task.updated_at = self._now()
        return task

    def _check_hook_errors(self, task_id: str, payload: dict[str, Any]) -> None:
        hook_errors = payload.get("hook_errors", [])
        if hook_errors:
            self._trace_recorder.record("hook_failed", task_id=task_id, detail={"hook_errors": hook_errors})

    def _assemble_context(self, task: TaskRun) -> AgentContext:
        ctx = self._context_assembler.assemble(
            task=task,
            available_tools=[spec.tool_name for spec in self._tool_gateway.list_tools()],
        )
        self._trace_recorder.record("context_assembled", task_id=task.task_id, detail={"available_tools": ctx.available_tools})
        return ctx

    def _active_planner(self) -> Any:
        """按 settings.planner_mode 选择规划器

        planner_mode=llm 时懒构建 LLMToolPlanner，以既有 KeywordPlanner
        作为降级规划器；默认 keyword 模式直接使用 KeywordPlanner，行为不变。
        """
        if getattr(settings, "planner_mode", "keyword") != "llm":
            return self._planner
        if self._llm_planner is None:
            from app.agent.nodes.llm_planner import LLMToolPlanner

            self._llm_planner = LLMToolPlanner(self._tool_gateway, fallback_planner=self._planner)
        return self._llm_planner

    def _plan(self, ctx: AgentContext) -> dict[str, Any]:
        plan_result = self._active_planner().plan(ctx.user_query)
        self._trace_recorder.record("plan_created", task_id=ctx.task_id, detail=plan_result)
        return plan_result

    def _execute(self, task: TaskRun, plan_result: dict[str, Any]) -> Any:
        tool_name = plan_result.get("tool_name")
        if not tool_name:
            return None

        arguments = plan_result.get("arguments") or {}
        spec = self._tool_gateway.get_tool(tool_name)
        if spec:
            decision = self._policy_engine.evaluate(tool_name, risk_level=spec.risk_level)
            if not decision["allowed"]:
                if decision.get("requires_approval"):
                    approval_store = self._get_approval_store()
                    if approval_store is not None:
                        approval = approval_store.create_approval(
                            task_id=task.task_id,
                            tool_name=tool_name,
                            action=f"调用工具 {tool_name}",
                            risk_level=spec.risk_level,
                            impact_scope=spec.permission_scope,
                            agent_reason=decision["reason"],
                            payload={
                                "mode": "keyword",
                                "query": task.query,
                                "tool_name": tool_name,
                                "arguments": arguments,
                                "plan_result": plan_result,
                            },
                        )
                        self._trace_recorder.record("approval_requested", task_id=task.task_id, detail={
                            "approval_id": approval.approval_id,
                            "tool_name": tool_name,
                            "risk_level": spec.risk_level.value,
                        })
                        task.status = TaskStatus.waiting_approval
                        return {
                            "blocked": True,
                            "requires_approval": True,
                            "approval_id": approval.approval_id,
                            "tool_name": tool_name,
                            "risk_level": spec.risk_level.value,
                            "reason": decision["reason"],
                        }
                self._trace_recorder.record("tool_called", task_id=task.task_id, detail={"tool_name": tool_name, "blocked": True, "reason": decision["reason"]})
                return {"blocked": True, "reason": decision["reason"], "tool_name": tool_name}

        hook_payload = self._hook_pipeline.run(HookStage.before_tool_call, {"task_id": task.task_id, "tool_name": tool_name})
        self._check_hook_errors(task.task_id, hook_payload)

        record = self._tool_gateway.call(tool_name, arguments=arguments, task_id=task.task_id)

        hook_payload = self._hook_pipeline.run(HookStage.after_tool_call, {"task_id": task.task_id, "tool_name": tool_name, "success": record.success})
        self._check_hook_errors(task.task_id, hook_payload)

        self._trace_recorder.record("tool_called", task_id=task.task_id, detail={"tool_name": tool_name, "success": record.success, "latency_ms": record.latency_ms, "error": record.error})
        return record

    def _verify(self, tool_result: Any) -> bool:
        if tool_result is None:
            return False
        if isinstance(tool_result, dict) and tool_result.get("blocked"):
            return False
        if hasattr(tool_result, "success"):
            return tool_result.success
        return True

    def _respond(self, plan_result: dict[str, Any], tool_result: Any, verified: bool) -> dict[str, Any]:
        if not plan_result.get("matched"):
            return {
                "answer": "抱歉，我暂时无法识别您的问题。当前支持查询：今日 GMV、本月新增用户、订单数量、Top 商品、退款率。",
                "tool_called": None,
                "success": False,
            }

        if isinstance(tool_result, dict) and tool_result.get("requires_approval"):
            return {
                "answer": f"工具调用需要人工审批：{tool_result['reason']}",
                "tool_called": tool_result.get("tool_name"),
                "success": False,
                "requires_approval": True,
                "approval_id": tool_result.get("approval_id"),
                "risk_level": tool_result.get("risk_level"),
                "blocked": True,
            }

        if isinstance(tool_result, dict) and tool_result.get("blocked"):
            return {
                "answer": f"工具调用被策略拦截：{tool_result['reason']}",
                "tool_called": tool_result.get("tool_name"),
                "success": False,
                "blocked": True,
            }

        if not verified:
            error_msg = ""
            if hasattr(tool_result, "error") and tool_result.error:
                error_msg = f"（{tool_result.error}）"
            return {
                "answer": f"工具调用失败{error_msg}，请稍后重试。",
                "tool_called": plan_result.get("tool_name"),
                "success": False,
            }

        data = tool_result.result if hasattr(tool_result, "result") else tool_result
        label = self._active_planner().get_label(plan_result.get("tool_name"))
        return {
            "answer": f"{label}查询结果：{data}",
            "tool_called": plan_result.get("tool_name"),
            "data": data,
            "success": True,
        }

    @staticmethod
    def _now():
        from datetime import datetime
        return datetime.now()

    def _get_approval_store(self):
        if self._approval_store is not None:
            return self._approval_store
        try:
            from app.main import get_approval_store
            return get_approval_store()
        except Exception:
            return None

    def _record_task_metrics(self, task: TaskRun, mode: str) -> None:
        if self._metrics_recorder is None:
            return
        try:
            status = "completed" if task.status == TaskStatus.completed else "failed"
            self._metrics_recorder.record_task(
                task_id=task.task_id,
                mode=mode,
                status=status,
            )
        except Exception:
            pass

    def _memory_add(self, session_id: str, role: str, content: str) -> None:
        if self._memory is None:
            return
        try:
            self._memory.add_message(session_id, role, content)
            self._trace_recorder.record("memory_message_added", task_id=session_id, detail={"role": role})
        except Exception:
            pass

    def _run_self_check(self, task: TaskRun) -> None:
        if self._self_check_engine is None:
            return
        try:
            task_result = task.result or {}
            reflection = self._self_check_engine.check(task_result)
            if task.result is None:
                task.result = {}
            task.result["reflection"] = reflection.model_dump()
            self._trace_recorder.record("reflection_completed", task_id=task.task_id, detail={
                "passed": reflection.passed,
                "score": reflection.score,
                "issue_count": len(reflection.issues),
            })
            if self._metrics_recorder is not None:
                self._metrics_recorder.reflection_count += 1
                if not reflection.passed:
                    self._metrics_recorder.reflection_failed_count += 1
        except Exception:
            pass
