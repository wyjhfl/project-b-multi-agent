from __future__ import annotations

from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.agent.nodes.planner import KeywordPlanner
from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.policy.operation_whitelist import OperationWhitelist
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, ToolSpec


def _build_runner() -> tuple[MultiAgentEvalRunner, TraceRecorder]:
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(
            tool_name="get_today_gmv",
            description="获取今日 GMV",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        lambda: type("R", (), {"success": True, "result": {"gmv": 100000}, "latency_ms": 10, "error": None})(),
    )
    whitelist = OperationWhitelist(gateway)
    engine = PolicyEngine(operation_whitelist=whitelist)
    recorder = TraceRecorder()
    planner = KeywordPlanner()
    executor = ExecutorAgent(
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)
    runner = MultiAgentEvalRunner(orchestrator, trace_recorder=recorder)
    return runner, recorder


def _build_runner_no_trace() -> MultiAgentEvalRunner:
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(
            tool_name="get_today_gmv",
            description="获取今日 GMV",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        lambda: type("R", (), {"success": True, "result": {"gmv": 100000}, "latency_ms": 10, "error": None})(),
    )
    whitelist = OperationWhitelist(gateway)
    engine = PolicyEngine(operation_whitelist=whitelist)
    planner = KeywordPlanner()
    executor = ExecutorAgent(
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=None)
    runner = MultiAgentEvalRunner(orchestrator, trace_recorder=None)
    return runner


class TestMultiAgentTrajectoryV11:

    def test_runner_outputs_trajectory_accuracy(self):
        runner, _ = _build_runner()
        result = runner.run()
        assert hasattr(result, "stats")
        assert hasattr(result.stats, "trajectory_passed")
        assert hasattr(result.stats, "trajectory_failed")
        assert hasattr(result.stats, "trajectory_accuracy")
        assert result.stats.trajectory_passed + result.stats.trajectory_failed >= 0
        assert 0.0 <= result.stats.trajectory_accuracy <= 1.0

    def test_security_case_trajectory(self):
        runner, _ = _build_runner()
        result = runner.run()
        security_cases = [c for c in runner.load_cases() if c.category == "security"]
        assert len(security_cases) >= 4
        for f in result.failures:
            if f.case_id.startswith("ma_injection"):
                assert f.trace_task_id is not None

    def test_failures_contain_trace_task_id(self):
        runner, _ = _build_runner()
        result = runner.run()
        for f in result.failures:
            assert f.trace_task_id is not None
            assert f.trace_task_id.startswith("eval_")

    def test_failures_contain_trajectory_issues_field(self):
        runner, _ = _build_runner()
        result = runner.run()
        for f in result.failures:
            assert isinstance(f.trajectory_issues, list)

    def test_hitl_case_category_exists(self):
        runner, _ = _build_runner()
        cases = runner.load_cases()
        hitl_cases = [c for c in cases if c.category == "hitl"]
        assert len(hitl_cases) >= 4

    def test_total_cases_at_least_24(self):
        runner, _ = _build_runner()
        cases = runner.load_cases()
        assert len(cases) >= 24


class TestNoTraceRecorderV11:

    def test_no_trace_recorder_not_fake_pass(self):
        runner = _build_runner_no_trace()
        result = runner.run()
        cases_with_traj = [c for c in runner.load_cases() if c.trajectory_expectation is not None]
        assert len(cases_with_traj) > 0
        assert result.stats.trajectory_failed > 0

    def test_no_trace_recorder_failure_stage_is_trajectory(self):
        runner = _build_runner_no_trace()
        result = runner.run()
        traj_failures = [f for f in result.failures if f.trajectory_issues]
        assert len(traj_failures) > 0
        for f in traj_failures:
            assert f.failure_stage == "trajectory"
            assert "trace_recorder missing" in f.trajectory_issues

    def test_no_trace_recorder_trajectory_accuracy_zero(self):
        runner = _build_runner_no_trace()
        result = runner.run()
        cases_with_traj = [c for c in runner.load_cases() if c.trajectory_expectation is not None]
        if len(cases_with_traj) > 0:
            assert result.stats.trajectory_passed == 0
            assert result.stats.trajectory_accuracy == 0.0
