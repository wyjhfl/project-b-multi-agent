from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.harness.eval.bad_cases import BadCase
from app.harness.eval.trajectory import TrajectoryEvaluator, TrajectoryExpectation


class MultiAgentEvalCase(BaseModel):
    case_id: str
    query: str
    expected_executed_mode: str | None = None
    expected_success: bool = True
    category: str = ""
    subcategory: str | None = None
    trajectory_expectation: TrajectoryExpectation | None = None


class EvalFailure(BaseModel):
    case_id: str
    query: str
    expected_executed_mode: str | None = None
    actual_executed_mode: str = ""
    expected_success: bool = True
    actual_success: bool = False
    reason: str = ""
    failure_stage: str | None = None
    trace_task_id: str | None = None
    trajectory_issues: list[str] = Field(default_factory=list)


class EvalStats(BaseModel):
    total: int = 0
    passed: int = 0
    accuracy: float = 0.0
    mode_confusion_count: int = 0
    trajectory_passed: int = 0
    trajectory_failed: int = 0
    trajectory_accuracy: float = 0.0


class MultiAgentEvalResult(BaseModel):
    total: int = 0
    passed: int = 0
    accuracy: float = 0.0
    failures: list[EvalFailure] = Field(default_factory=list)
    mode_confusion_count: int = 0
    bad_cases: list[BadCase] = Field(default_factory=list)
    stats: EvalStats = Field(default_factory=EvalStats)


class MultiAgentEvalRunner:
    CASES_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "evaluation", "multi_agent_cases.json"
    )

    def __init__(self, orchestrator: Any, trace_recorder: Any | None = None) -> None:
        self._orchestrator = orchestrator
        self._trace_recorder = trace_recorder
        self._trajectory_evaluator = TrajectoryEvaluator()
        self._last_result: MultiAgentEvalResult | None = None

    def load_cases(self) -> list[MultiAgentEvalCase]:
        with open(self.CASES_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return [MultiAgentEvalCase(**c) for c in raw]

    def run(self, generator: str = "mock", provider: str | None = None, fallback_to_mock: bool = True) -> MultiAgentEvalResult:
        cases = self.load_cases()
        total = len(cases)
        passed = 0
        failures: list[EvalFailure] = []
        bad_cases: list[BadCase] = []
        mode_confusion_count = 0
        trajectory_passed = 0
        trajectory_failed = 0

        for case in cases:
            trace_task_id = f"eval_{case.case_id}"

            if self._trace_recorder is not None:
                self._trace_recorder.clear()

            result = self._orchestrator.run(
                query=case.query,
                task_id=trace_task_id,
                generator=generator,
                provider=provider,
                fallback_to_mock=fallback_to_mock,
            )

            actual_mode = result.executed_mode
            actual_success = result.success

            mode_ok = True
            if case.expected_executed_mode is not None:
                mode_ok = actual_mode == case.expected_executed_mode
                if not mode_ok:
                    mode_confusion_count += 1

            success_ok = actual_success == case.expected_success

            trajectory_issues: list[str] = []
            failure_stage: str | None = None

            if case.trajectory_expectation is not None and self._trace_recorder is not None:
                trace_events_raw = self._trace_recorder.get_events(task_id=trace_task_id)
                trace_events = [
                    {"event_type": e.event_type, "detail": e.detail or {}}
                    for e in trace_events_raw
                ]
                traj_result = self._trajectory_evaluator.evaluate(trace_events, case.trajectory_expectation)
                if traj_result.passed:
                    trajectory_passed += 1
                else:
                    trajectory_failed += 1
                    trajectory_issues = traj_result.issues
                    if trajectory_issues:
                        failure_stage = "trajectory"
            elif case.trajectory_expectation is not None:
                trajectory_failed += 1
                trajectory_issues = ["trace_recorder missing"]
                failure_stage = "trajectory"

            if mode_ok and success_ok and not trajectory_issues:
                passed += 1
            else:
                reason_parts: list[str] = []
                if not mode_ok:
                    reason_parts.append(f"mode 期望 {case.expected_executed_mode} 实际 {actual_mode}")
                    failure_stage = failure_stage or "mode"
                if not success_ok:
                    reason_parts.append(f"success 期望 {case.expected_success} 实际 {actual_success}")
                    failure_stage = failure_stage or "outcome"
                if trajectory_issues:
                    reason_parts.append(f"trajectory: {'; '.join(trajectory_issues)}")
                reason = "; ".join(reason_parts)

                failures.append(EvalFailure(
                    case_id=case.case_id,
                    query=case.query,
                    expected_executed_mode=case.expected_executed_mode,
                    actual_executed_mode=actual_mode,
                    expected_success=case.expected_success,
                    actual_success=actual_success,
                    reason=reason,
                    failure_stage=failure_stage,
                    trace_task_id=trace_task_id,
                    trajectory_issues=trajectory_issues,
                ))

                bad_cases.append(BadCase(
                    suite="multi_agent",
                    case_id=case.case_id,
                    query=case.query,
                    expected=self._format_expected(case),
                    actual=f"mode={actual_mode}, success={actual_success}",
                    reason=reason,
                    trace_task_id=trace_task_id,
                    created_at=datetime.now(),
                ))

        accuracy = round(passed / total, 4) if total > 0 else 0.0
        traj_total = trajectory_passed + trajectory_failed
        trajectory_accuracy = round(trajectory_passed / traj_total, 4) if traj_total > 0 else 0.0

        stats = EvalStats(
            total=total,
            passed=passed,
            accuracy=accuracy,
            mode_confusion_count=mode_confusion_count,
            trajectory_passed=trajectory_passed,
            trajectory_failed=trajectory_failed,
            trajectory_accuracy=trajectory_accuracy,
        )
        result_obj = MultiAgentEvalResult(
            total=total,
            passed=passed,
            accuracy=accuracy,
            failures=failures,
            mode_confusion_count=mode_confusion_count,
            bad_cases=bad_cases,
            stats=stats,
        )
        self._last_result = result_obj
        return result_obj

    def export_bad_cases(self) -> list[BadCase]:
        if self._last_result is not None:
            return list(self._last_result.bad_cases)
        return []

    def _format_expected(self, case: MultiAgentEvalCase) -> str:
        parts = []
        if case.expected_executed_mode is not None:
            parts.append(f"mode={case.expected_executed_mode}")
        parts.append(f"success={case.expected_success}")
        return ", ".join(parts)
