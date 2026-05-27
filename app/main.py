from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.agent.graph.kernel import AgentKernel
from app.agent.graph.runtime_adapter import GraphRuntimeAdapter
from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.agent.nodes.planner import KeywordPlanner
from app.harness.audit.recorder import AuditRecorder
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.harness.memory.short_term import ShortTermMemory
from app.harness.reflection.self_check import SelfCheckEngine
from app.harness.skills.registry import SkillRegistry
from app.harness.policy.engine import PolicyEngine
from app.harness.policy.operation_whitelist import OperationWhitelist
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, ToolSpec
from app.services.multitool_pipeline import MultiToolPipeline
from app.services.nl2sql_pipeline import NL2SQLPipeline
from app.storage import factory as store_factory
from app.tools.local.ops_query import (
    get_month_new_users,
    get_order_count,
    get_refund_rate,
    get_today_gmv,
    get_top_products,
)
from app.tools.mcp.client import FakeMCPClient
from app.core.config import settings
from app.core.request_guards import BasicAbuseGuardMiddleware, RateLimitMiddleware, RequestSizeLimitMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware, build_cors_options

_kernel: AgentKernel | None = None
_trace_recorder: TraceRecorder | None = None
_planner: KeywordPlanner | None = None
_gateway: ToolGateway | None = None
_policy_engine: PolicyEngine | None = None
_task_store = None
_orchestrator: MultiAgentOrchestrator | None = None
_approval_store = None
_audit_store = None
_audit_recorder: AuditRecorder | None = None
_metrics_recorder: RuntimeMetricsRecorder | None = None
_metrics_store = None
_memory: ShortTermMemory | None = None
_skill_registry: SkillRegistry | None = None
_graph_checkpoint_store = None
_graph_runtime_adapter: GraphRuntimeAdapter | None = None


def _build_runtime() -> tuple[AgentKernel, TraceRecorder, KeywordPlanner, ToolGateway, PolicyEngine]:
    global _kernel, _trace_recorder, _planner, _gateway, _policy_engine, _orchestrator, _approval_store, _audit_store, _audit_recorder, _metrics_recorder, _metrics_store, _memory, _graph_checkpoint_store, _graph_runtime_adapter

    assembler = ContextAssembler()
    gateway = ToolGateway()
    pipeline = HookPipeline()
    recorder = TraceRecorder()
    planner = KeywordPlanner()
    nl2sql_pipeline = NL2SQLPipeline()

    _register_tools(gateway)
    _register_mcp_tools(gateway)

    whitelist = OperationWhitelist(gateway)
    engine = PolicyEngine(operation_whitelist=whitelist)

    if _approval_store is None:
        _approval_store = get_approval_store()

    if _audit_store is None:
        _audit_store = get_audit_store()
    if _audit_recorder is None:
        _audit_recorder = AuditRecorder(_audit_store)

    if _metrics_recorder is None:
        _metrics_recorder = RuntimeMetricsRecorder()

    if _metrics_store is None:
        _metrics_store = get_metrics_store()

    _metrics_recorder.set_metrics_store(_metrics_store)

    if _memory is None:
        _memory = ShortTermMemory()

    gateway.set_metrics_recorder(_metrics_recorder)
    nl2sql_pipeline.set_metrics_recorder(_metrics_recorder)

    multitool_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=_approval_store, audit_recorder=_audit_recorder)

    if _graph_checkpoint_store is None:
        _graph_checkpoint_store = get_graph_checkpoint_store()
    _graph_runtime_adapter = GraphRuntimeAdapter(
        context_assembler=assembler,
        gateway=gateway,
        policy_engine=engine,
        checkpoint_store=_graph_checkpoint_store,
        trace_recorder=recorder,
        planner=planner,
        approval_store=_approval_store,
        audit_recorder=_audit_recorder,
    )

    executor = ExecutorAgent(
        nl2sql_pipeline=nl2sql_pipeline,
        multitool_pipeline=multitool_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    _trace_recorder = recorder
    _planner = planner
    _gateway = gateway
    _policy_engine = engine
    _orchestrator = orchestrator
    _kernel = AgentKernel(
        context_assembler=assembler,
        tool_gateway=gateway,
        hook_pipeline=pipeline,
        policy_engine=engine,
        trace_recorder=recorder,
        planner=planner,
        nl2sql_pipeline=nl2sql_pipeline,
        multitool_pipeline=multitool_pipeline,
        multi_agent_orchestrator=orchestrator,
        approval_store=_approval_store,
        graph_runtime_adapter=_graph_runtime_adapter,
    )
    _kernel.set_metrics_recorder(_metrics_recorder)
    _kernel.set_memory(_memory)
    _kernel.set_self_check_engine(SelfCheckEngine())
    return _kernel, _trace_recorder, _planner, _gateway, _policy_engine


def _register_tools(gateway: ToolGateway) -> None:
    gateway.register(
        ToolSpec(
            tool_name="get_today_gmv",
            description="获取今日 GMV",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"date": {"type": "string"}, "gmv": {"type": "number"}, "currency": {"type": "string"}}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        get_today_gmv,
    )
    gateway.register(
        ToolSpec(
            tool_name="get_month_new_users",
            description="获取本月新增用户数",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"year": {"type": "integer"}, "month": {"type": "integer"}, "new_users": {"type": "integer"}}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        get_month_new_users,
    )
    gateway.register(
        ToolSpec(
            tool_name="get_order_count",
            description="获取订单数量",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"date": {"type": "string"}, "order_count": {"type": "integer"}}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        get_order_count,
    )
    gateway.register(
        ToolSpec(
            tool_name="get_top_products",
            description="获取 Top 商品",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}},
            output_schema={"type": "object", "properties": {"top_products": {"type": "array"}, "count": {"type": "integer"}}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        get_top_products,
    )
    gateway.register(
        ToolSpec(
            tool_name="get_refund_rate",
            description="获取退款率",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"total_orders": {"type": "integer"}, "refund_count": {"type": "integer"}, "refund_rate_percent": {"type": "number"}}},
            risk_level=RiskLevel.medium,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        get_refund_rate,
    )


def _register_mcp_tools(gateway: ToolGateway) -> None:
    import logging
    from app.core.config import settings

    mcp_mode = settings.mcp_mode

    if mcp_mode == "real":
        try:
            from app.tools.mcp.stdio_client import StdioMCPClient

            client = StdioMCPClient(
                server_name=settings.mcp_server_name,
                command=settings.mcp_server_command,
                args=settings.mcp_server_args,
                timeout_seconds=settings.mcp_server_timeout_seconds,
                workdir=settings.mcp_server_workdir,
                env_allowlist=settings.mcp_server_env_allowlist,
                command_allowlist=settings.mcp_server_command_allowlist,
            )
            gateway.register_mcp_server(settings.mcp_server_name, client)
            discovered = gateway.discover_mcp_tools(settings.mcp_server_name)
            if not discovered:
                logging.warning(
                    "MCP_MODE=real 但 StdioMCPClient 未发现任何工具，"
                    "请检查 MCP_SERVER_COMMAND 配置"
                )
        except Exception as exc:
            logging.warning(
                "MCP_MODE=real 注册失败: %s，服务仍可启动（仅 local tools 可用）",
                exc,
            )
    else:
        fake_client = FakeMCPClient()
        gateway.register_mcp_server("fake_ops_mcp", fake_client)
        gateway.discover_mcp_tools("fake_ops_mcp")


def get_kernel() -> AgentKernel:
    if _kernel is None:
        k, _, _, _, _ = _build_runtime()
        return k
    return _kernel


def get_trace_recorder() -> TraceRecorder:
    if _trace_recorder is None:
        _, r, _, _, _ = _build_runtime()
        return r
    return _trace_recorder


def get_planner() -> KeywordPlanner:
    if _planner is None:
        _, _, p, _, _ = _build_runtime()
        return p
    return _planner


def get_gateway() -> ToolGateway:
    if _gateway is None:
        _, _, _, g, _ = _build_runtime()
        return g
    return _gateway


def get_policy_engine() -> PolicyEngine:
    if _policy_engine is None:
        _, _, _, _, e = _build_runtime()
        return e
    return _policy_engine


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    if _orchestrator is None:
        _build_runtime()
    return _orchestrator


def get_task_store():
    global _task_store
    if _task_store is None:
        _task_store = store_factory.get_task_store()
    return _task_store


def get_approval_store():
    global _approval_store
    if _approval_store is None:
        _approval_store = store_factory.get_approval_store()
    return _approval_store


def get_audit_store():
    global _audit_store
    if _audit_store is None:
        _audit_store = store_factory.get_audit_store()
    return _audit_store


def get_audit_recorder() -> AuditRecorder:
    global _audit_recorder, _audit_store
    if _audit_recorder is None:
        if _audit_store is None:
            _audit_store = get_audit_store()
        _audit_recorder = AuditRecorder(_audit_store)
    return _audit_recorder


def get_metrics_recorder() -> RuntimeMetricsRecorder:
    global _metrics_recorder
    if _metrics_recorder is None:
        _metrics_recorder = RuntimeMetricsRecorder()
    return _metrics_recorder


def get_metrics_store():
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = store_factory.get_metrics_store()
    return _metrics_store


def get_graph_checkpoint_store():
    global _graph_checkpoint_store
    if _graph_checkpoint_store is None:
        _graph_checkpoint_store = store_factory.get_graph_checkpoint_store()
    return _graph_checkpoint_store


def get_memory() -> ShortTermMemory:
    global _memory
    if _memory is None:
        _memory = ShortTermMemory()
    return _memory


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


def reset_runtime_for_test() -> None:
    global _kernel, _trace_recorder, _planner, _gateway, _policy_engine, _task_store, _orchestrator, _approval_store, _audit_store, _audit_recorder, _metrics_recorder, _metrics_store, _memory, _skill_registry, _graph_checkpoint_store, _graph_runtime_adapter
    _kernel = None
    _trace_recorder = None
    _planner = None
    _gateway = None
    _policy_engine = None
    _task_store = None
    _orchestrator = None
    _approval_store = None
    _audit_store = None
    _audit_recorder = None
    _metrics_recorder = None
    _metrics_store = None
    _memory = None
    _skill_registry = None
    _graph_checkpoint_store = None
    _graph_runtime_adapter = None
    try:
        from app.harness.llm import reset_llm_budget_manager_for_test, reset_llm_result_cache_for_test

        reset_llm_budget_manager_for_test()
        reset_llm_result_cache_for_test()
    except Exception:
        pass
    try:
        import app.storage.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None
    except Exception:
        pass


app = FastAPI(
    title="Project B: Harness-native 运营中台 Agent",
    version="2.9.0",
)

app.add_middleware(BasicAbuseGuardMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware, enabled=settings.security_headers_enabled)

if settings.cors_enabled:
    app.add_middleware(CORSMiddleware, **build_cors_options(settings))

app.add_middleware(RequestLoggingMiddleware)

from app.api.tasks import router as tasks_router
from app.api.nl2sql import router as nl2sql_router
from app.api.tools import router as tools_router
from app.api.multi_agent_eval import router as multi_agent_eval_router
from app.api.observability import router as observability_router
from app.api.eval_summary import router as eval_summary_router
from app.api.approval_ui import router as approval_ui_router
from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.metrics import router as metrics_router
from app.api.bad_cases import router as bad_cases_router
from app.api.memory_api import router as memory_router
from app.api.skills_api import router as skills_router
from app.api.reflection_api import router as reflection_router
from app.api.runtime_snapshot import router as runtime_snapshot_router
from app.api.auth import router as auth_router
from app.api.oidc import router as oidc_router
from app.api.llm_acceptance import router as llm_acceptance_router
from app.api.llm_pilot import router as llm_pilot_router
from app.api.deployment import router as deployment_router

app.include_router(tasks_router)
app.include_router(nl2sql_router)
app.include_router(tools_router)
app.include_router(multi_agent_eval_router)
app.include_router(observability_router)
app.include_router(eval_summary_router)
app.include_router(approval_ui_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(metrics_router)
app.include_router(bad_cases_router)
app.include_router(memory_router)
app.include_router(skills_router)
app.include_router(reflection_router)
app.include_router(runtime_snapshot_router)
app.include_router(auth_router)
app.include_router(oidc_router)
app.include_router(llm_acceptance_router)
app.include_router(llm_pilot_router)
app.include_router(deployment_router)


@app.get("/health")
async def health_check():
    from app.cache.redis_client import check_redis_health
    redis_status = check_redis_health()
    return {
        "status": "ok",
        "service": "project-b-multi-agent",
        "version": "2.9.0",
        "storage_backend": settings.storage_backend,
        "auth_enabled": settings.auth_enabled,
        "rbac_enabled": settings.rbac_enabled,
        "redis": redis_status,
    }
