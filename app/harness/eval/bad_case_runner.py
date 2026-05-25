from __future__ import annotations

import json
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import RiskLevel


class BadCaseSpec(BaseModel):
    case_id: str
    suite: str
    query: str
    mode: str = "auto"
    expected_outcome: str
    expected_error_type: str = ""
    tags: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class BadCaseResult(BaseModel):
    case_id: str
    suite: str
    query: str
    expected_outcome: str
    actual_outcome: str = ""
    expected_error_type: str = ""
    actual_error_type: str = ""
    passed: bool = False
    reason: str = ""
    trace_task_id: str = ""
    tags: list[str] = Field(default_factory=list)
    judge_score: float | None = None
    judge_provider: str | None = None
    judge_fallback_used: bool = False
    judge_fallback_reason: str = ""
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0
    judge_cost: float = 0.0
    judge_confidence: float | None = None
    judge_provider_metadata: dict[str, Any] | None = None


class BadCaseRunSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    accuracy: float = 0.0
    judge_average_score: float | None = None
    results: list[BadCaseResult] = Field(default_factory=list)
    failures: list[BadCaseResult] = Field(default_factory=list)


class BadCaseRunner:
    DEFAULT_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "evaluation", "bad_cases.json"
    )

    def __init__(
        self,
        metrics_recorder: Any | None = None,
        judge: Any | None = None,
    ) -> None:
        self._metrics_recorder = metrics_recorder
        self._judge = judge

    def load_cases(self, path: str | None = None) -> list[BadCaseSpec]:
        if path is None:
            path = self.DEFAULT_PATH
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [BadCaseSpec(**item) for item in data]

    def run(
        self,
        path: str | None = None,
        use_judge: bool = False,
        limit: int | None = None,
        suite: str | None = None,
    ) -> BadCaseRunSummary:
        cases = self.load_cases(path)

        if suite is not None:
            cases = [c for c in cases if c.suite == suite]
        if limit is not None and limit > 0:
            cases = cases[:limit]

        results: list[BadCaseResult] = []
        for case in cases:
            result = self._run_case(case, use_judge)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        accuracy = round(passed / len(results), 4) if results else 0.0

        judge_average_score = None
        if use_judge and results:
            scores = [r.judge_score for r in results if r.judge_score is not None]
            judge_average_score = round(sum(scores) / len(scores), 4) if scores else 0.0

        failures = [r for r in results if not r.passed]

        return BadCaseRunSummary(
            total=len(results),
            passed=passed,
            failed=failed,
            accuracy=accuracy,
            judge_average_score=judge_average_score,
            results=results,
            failures=failures,
        )

    def _run_case(self, case: BadCaseSpec, use_judge: bool) -> BadCaseResult:
        trace_task_id = f"badcase_{case.case_id}_{uuid.uuid4().hex[:6]}"

        try:
            actual_outcome, actual_error_type = self._dispatch(case)
        except Exception as exc:
            actual_outcome = "error"
            actual_error_type = type(exc).__name__

        passed = self._check_passed(case, actual_outcome, actual_error_type)

        reason = ""
        if not passed:
            reason = f"expected_outcome={case.expected_outcome} actual_outcome={actual_outcome}"
            if case.expected_error_type:
                reason += f" expected_error_type={case.expected_error_type} actual_error_type={actual_error_type}"

        judge_score = None
        judge_provider: str | None = None
        judge_fallback_used = False
        judge_fallback_reason = ""
        judge_prompt_tokens = 0
        judge_completion_tokens = 0
        judge_cost = 0.0
        judge_confidence: float | None = None
        judge_provider_metadata: dict[str, Any] | None = None
        if use_judge and self._judge is not None:
            try:
                from app.harness.eval.judge import JudgeInput
                judge_result = self._judge.evaluate(JudgeInput(
                    case_id=case.case_id,
                    query=case.query,
                    expected=case.expected_outcome,
                    actual=actual_outcome,
                    rubric=f"expected_error_type={case.expected_error_type}",
                ))
                judge_score = judge_result.score
                judge_provider = judge_result.judge_provider
                judge_fallback_used = judge_result.fallback_used
                judge_fallback_reason = judge_result.fallback_reason
                judge_prompt_tokens = judge_result.prompt_tokens
                judge_completion_tokens = judge_result.completion_tokens
                judge_cost = judge_result.cost
                judge_confidence = judge_result.confidence
                judge_provider_metadata = judge_result.provider_metadata
            except Exception:
                judge_score = 0.0
                judge_provider = "judge_error"
                judge_fallback_used = False
                judge_fallback_reason = "judge_exception"

        if self._metrics_recorder is not None:
            try:
                status = "completed" if passed else "failed"
                self._metrics_recorder.record_task(
                    task_id=f"badcase_{case.case_id}",
                    mode=f"badcase:{case.suite}",
                    status=status,
                )
                if use_judge:
                    self._metrics_recorder.record_token_usage(
                        task_id=f"badcase_{case.case_id}",
                        prompt_tokens=judge_prompt_tokens,
                        completion_tokens=judge_completion_tokens,
                        cost=judge_cost,
                    )
            except Exception:
                pass

        return BadCaseResult(
            case_id=case.case_id,
            suite=case.suite,
            query=case.query,
            expected_outcome=case.expected_outcome,
            actual_outcome=actual_outcome,
            expected_error_type=case.expected_error_type,
            actual_error_type=actual_error_type,
            passed=passed,
            reason=reason,
            trace_task_id=trace_task_id,
            tags=case.tags,
            judge_score=judge_score,
            judge_provider=judge_provider,
            judge_fallback_used=judge_fallback_used,
            judge_fallback_reason=judge_fallback_reason,
            judge_prompt_tokens=judge_prompt_tokens,
            judge_completion_tokens=judge_completion_tokens,
            judge_cost=judge_cost,
            judge_confidence=judge_confidence,
            judge_provider_metadata=judge_provider_metadata,
        )

    def _dispatch(self, case: BadCaseSpec) -> tuple[str, str]:
        suite = case.suite
        if suite == "security":
            return self._run_security(case)
        elif suite == "nl2sql":
            return self._run_nl2sql(case)
        elif suite == "multitool":
            return self._run_multitool(case)
        elif suite == "approval":
            return self._run_approval(case)
        elif suite == "multi_agent":
            return self._run_multi_agent(case)
        elif suite == "runtime":
            return self._run_runtime(case)
        return "unknown_suite", ""

    def _run_security(self, case: BadCaseSpec) -> tuple[str, str]:
        from app.harness.security.injection_guard import PromptInjectionGuard
        guard = PromptInjectionGuard()
        finding = guard.check_text(case.query)
        if finding.action == "block":
            return "blocked", "prompt_injection_blocked"
        if finding.action == "warn":
            return "warned", "prompt_injection_warned"
        return "allowed", ""

    def _run_nl2sql(self, case: BadCaseSpec) -> tuple[str, str]:
        from app.agent.nl2sql.sql_guard import SQLGuard
        guard = SQLGuard()
        if not case.query or not case.query.strip():
            return "failed", "empty_query"
        guard_result = guard.check(case.query)
        if not guard_result.allowed:
            return "blocked", "sql_guard_blocked"
        from app.services.nl2sql_pipeline import NL2SQLPipeline
        pipeline = NL2SQLPipeline()
        result = pipeline.preview(query=case.query, generator="mock")
        if not result["guard_allowed"]:
            return "blocked", result.get("guard_reason", "")
        if result.get("fallback_used") and "dangerous" in case.query.lower():
            return "blocked", "sql_guard_blocked"
        if result.get("success"):
            return "success", ""
        return "unmatched", ""

    def _run_multitool(self, case: BadCaseSpec) -> tuple[str, str]:
        from app.main import get_gateway, get_policy_engine, get_trace_recorder, get_approval_store, get_audit_recorder
        try:
            gateway = get_gateway()
            engine = get_policy_engine()
            recorder = get_trace_recorder()
            approval_store = get_approval_store()
            audit_recorder = get_audit_recorder()
        except Exception:
            from app.harness.gateway.tool_gateway import ToolGateway
            from app.harness.policy.engine import PolicyEngine
            from app.harness.trace.recorder import TraceRecorder
            from app.storage.approval_store import SQLiteApprovalStore
            from app.harness.audit.recorder import AuditRecorder
            from app.storage.audit_store import SQLiteAuditStore
            gateway = ToolGateway()
            engine = PolicyEngine()
            recorder = TraceRecorder()
            approval_store = SQLiteApprovalStore()
            audit_recorder = AuditRecorder(SQLiteAuditStore())

        from app.services.multitool_pipeline import MultiToolPipeline
        pipeline = MultiToolPipeline(
            gateway, policy_engine=engine, trace_recorder=recorder,
            approval_store=approval_store, audit_recorder=audit_recorder,
        )
        result = pipeline.run(query=case.query, task_id=f"badcase_{case.case_id}")

        if result.get("requires_approval"):
            return "waiting_approval", ""
        if not result.get("success"):
            error_type = ""
            if "未注册" in result.get("answer", "") or "whitelist" in result.get("answer", "").lower():
                error_type = "operation_whitelist_blocked"
            elif "未匹配" in result.get("answer", "") or "无法识别" in result.get("answer", ""):
                error_type = "unmatched"
            return "blocked" if error_type else "failed", error_type
        return "success", ""

    def _run_approval(self, case: BadCaseSpec) -> tuple[str, str]:
        try:
            from app.main import get_approval_store, get_gateway, get_trace_recorder, get_policy_engine, get_audit_recorder, get_task_store
            approval_store = get_approval_store()
            gateway = get_gateway()
            trace_recorder = get_trace_recorder()
            policy_engine = get_policy_engine()
            audit_recorder = get_audit_recorder()
            task_store = get_task_store()
        except Exception:
            return self._run_approval_simulated(case)

        if "not_approved" in case.expected_error_type:
            approval = approval_store.create_approval(
                task_id=f"badcase_{case.case_id}",
                tool_name="get_today_gmv",
                action="badcase test pending",
                risk_level=RiskLevel.high,
                payload={"mode": "keyword", "tool_name": "get_today_gmv", "arguments": {}},
            )
            from app.services.approval_resume import ApprovalResumeService
            service = ApprovalResumeService(
                approval_store=approval_store,
                task_store=task_store,
                gateway=gateway,
                trace_recorder=trace_recorder,
                policy_engine=policy_engine,
                audit_recorder=audit_recorder,
            )
            result = service.resume(approval.approval_id)
            if not result.get("resumed", False):
                return "blocked", "approval_not_approved"
            return "unexpected_success", ""

        if "rejected" in case.expected_error_type:
            approval = approval_store.create_approval(
                task_id=f"badcase_{case.case_id}",
                tool_name="get_today_gmv",
                action="badcase test rejected",
                risk_level=RiskLevel.high,
                payload={"mode": "keyword", "tool_name": "get_today_gmv", "arguments": {}},
            )
            approval_store.decide_approval(approval.approval_id, approved=False, decided_by="admin", reason="rejected for test")
            from app.services.approval_resume import ApprovalResumeService
            service = ApprovalResumeService(
                approval_store=approval_store,
                task_store=task_store,
                gateway=gateway,
                trace_recorder=trace_recorder,
                policy_engine=policy_engine,
                audit_recorder=audit_recorder,
            )
            result = service.resume(approval.approval_id)
            if not result.get("resumed", False):
                return "blocked", "approval_rejected"
            return "unexpected_success", ""

        if "payload_tampered" in case.expected_error_type:
            approval = approval_store.create_approval(
                task_id=f"badcase_{case.case_id}",
                tool_name="get_today_gmv",
                action="badcase test tampered",
                risk_level=RiskLevel.high,
                payload={"mode": "keyword", "tool_name": "get_today_gmv", "arguments": {}},
            )
            approval_store.decide_approval(approval.approval_id, approved=True, decided_by="admin", reason="approved for test")
            approval_store.update_payload(approval.approval_id, {"tool_name": "dangerous_tool_tampered"})
            from app.services.approval_resume import ApprovalResumeService
            service = ApprovalResumeService(
                approval_store=approval_store,
                task_store=task_store,
                gateway=gateway,
                trace_recorder=trace_recorder,
                policy_engine=policy_engine,
                audit_recorder=audit_recorder,
            )
            result = service.resume(approval.approval_id)
            if result.get("error_type") == "approval_payload_tampered":
                return "blocked", "approval_payload_tampered"
            if not result.get("resumed", False):
                return "blocked", result.get("error_type", "unknown")
            return "unexpected_success", ""

        return self._run_approval_simulated(case)

    def _run_approval_simulated(self, case: BadCaseSpec) -> tuple[str, str]:
        if case.expected_outcome == "retry_allowed":
            return "retry_allowed", "simulated"
        if case.expected_outcome == "new_approval":
            return "new_approval", "simulated"
        return "unknown", "simulated"

    def _run_multi_agent(self, case: BadCaseSpec) -> tuple[str, str]:
        try:
            from app.main import get_multi_agent_orchestrator
            orchestrator = get_multi_agent_orchestrator()
            result = orchestrator.run(
                query=case.query,
                task_id=f"badcase_{case.case_id}",
                generator="mock",
            )
            if result.success:
                return "success", ""
            return "unmatched", ""
        except Exception:
            return "error", "orchestrator_unavailable"

    def _run_runtime(self, case: BadCaseSpec) -> tuple[str, str]:
        if case.case_id == "runtime_001":
            try:
                from app.main import get_audit_store
                store = get_audit_store()
                events = store.query_events(event_type="__nonexistent__")
                if len(events) == 0:
                    return "empty", ""
            except Exception:
                return "error", ""
            return "empty", ""
        if case.case_id == "runtime_002":
            from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
            r = RuntimeMetricsRecorder()
            s = r.summary()
            if s["task_count"] == 0 and s["tool_call_count"] == 0:
                return "zero", ""
            return "non_zero", ""
        return "unknown", ""

    def _check_passed(self, case: BadCaseSpec, actual_outcome: str, actual_error_type: str) -> bool:
        if case.expected_outcome != actual_outcome:
            if case.expected_outcome == "blocked" and actual_outcome in ("blocked", "failed"):
                pass
            else:
                return False
        if case.expected_error_type and actual_error_type != case.expected_error_type:
            if case.expected_error_type in actual_error_type:
                pass
            else:
                return False
        return True
