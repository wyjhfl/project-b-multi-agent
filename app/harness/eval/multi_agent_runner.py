from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.harness.eval.bad_cases import BadCase


class MultiAgentEvalCase(BaseModel):
    case_id: str
    query: str
    expected_executed_mode: str | None = None
    expected_success: bool = True


class EvalFailure(BaseModel):
    case_id: str
    query: str
    expected_executed_mode: str | None = None
    actual_executed_mode: str = ""
    expected_success: bool = True
    actual_success: bool = False
    reason: str = ""
    trace_task_id: str | None = None


class MultiAgentEvalResult(BaseModel):
    total: int = 0
    passed: int = 0
    accuracy: float = 0.0
    failures: list[EvalFailure] = Field(default_factory=list)
    mode_confusion_count: int = 0
    bad_cases: list[BadCase] = Field(default_factory=list)


class MultiAgentEvalRunner:
    CASES_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "evaluation", "multi_agent_cases.json"
    )

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator
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

        for case in cases:
            trace_task_id = f"eval_{case.case_id}"
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

            if mode_ok and success_ok:
                passed += 1
            else:
                reason_parts: list[str] = []
                if not mode_ok:
                    reason_parts.append(f"mode 期望 {case.expected_executed_mode} 实际 {actual_mode}")
                if not success_ok:
                    reason_parts.append(f"success 期望 {case.expected_success} 实际 {actual_success}")
                reason = "; ".join(reason_parts)

                failures.append(EvalFailure(
                    case_id=case.case_id,
                    query=case.query,
                    expected_executed_mode=case.expected_executed_mode,
                    actual_executed_mode=actual_mode,
                    expected_success=case.expected_success,
                    actual_success=actual_success,
                    reason=reason,
                    trace_task_id=trace_task_id,
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
        result = MultiAgentEvalResult(
            total=total,
            passed=passed,
            accuracy=accuracy,
            failures=failures,
            mode_confusion_count=mode_confusion_count,
            bad_cases=bad_cases,
        )
        self._last_result = result
        return result

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
