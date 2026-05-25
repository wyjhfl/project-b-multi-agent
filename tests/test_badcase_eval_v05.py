from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.harness.eval.bad_case_runner import BadCaseRunner, BadCaseSpec
from app.harness.eval.judge import FakeJudge, JudgeInput, LLMJudgeProvider, JudgeResult
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.core.config import settings
from app.main import app, reset_runtime_for_test

BAD_CASES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "evaluation", "bad_cases.json"
)

client = TestClient(app)


def test_bad_cases_json_count():
    with open(BAD_CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 30


def test_bad_case_runner_load_all():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    assert len(cases) >= 30


def test_security_injection_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    security_cases = [c for c in cases if c.suite == "security"]
    assert len(security_cases) >= 8

    for case in security_cases:
        result = runner._run_case(case, use_judge=False)
        if case.expected_outcome == "blocked":
            assert result.actual_outcome == "blocked", f"case {case.case_id}: expected blocked, got {result.actual_outcome}"


def test_nl2sql_dangerous_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    dangerous = [c for c in cases if c.suite == "nl2sql" and c.expected_outcome == "blocked"]
    assert len(dangerous) >= 1

    for case in dangerous:
        result = runner._run_case(case, use_judge=False)
        assert result.actual_outcome == "blocked", f"case {case.case_id}: expected blocked, got {result.actual_outcome}"


def test_multitool_unknown_tool_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    unknown_tool = [c for c in cases if c.suite == "multitool" and "whitelist" in c.expected_error_type]
    assert len(unknown_tool) >= 1

    for case in unknown_tool:
        result = runner._run_case(case, use_judge=False)
        assert result.actual_outcome in ("blocked", "failed"), f"case {case.case_id}: got {result.actual_outcome}"


def test_approval_payload_tampered_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    tampered = [c for c in cases if c.suite == "approval" and "payload_tampered" in c.expected_error_type]
    assert len(tampered) >= 1

    for case in tampered:
        result = runner._run_case(case, use_judge=False)
        assert result.actual_outcome == "blocked", f"case {case.case_id}: expected blocked, got {result.actual_outcome}"
        assert result.actual_error_type == "approval_payload_tampered"


def test_multi_agent_unknown_query_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    unknown = [c for c in cases if c.suite == "multi_agent" and c.expected_outcome == "unmatched"]
    assert len(unknown) >= 1

    for case in unknown:
        result = runner._run_case(case, use_judge=False)
        assert result.actual_outcome in ("unmatched", "error"), f"case {case.case_id}: got {result.actual_outcome}"


def test_runtime_zero_metrics_case_passes():
    runner = BadCaseRunner()
    cases = runner.load_cases()
    runtime_cases = [c for c in cases if c.suite == "runtime"]
    assert len(runtime_cases) >= 2

    for case in runtime_cases:
        result = runner._run_case(case, use_judge=False)
        assert result.actual_outcome in ("zero", "empty"), f"case {case.case_id}: got {result.actual_outcome}"


def test_fake_judge_expected_equals_actual():
    judge = FakeJudge()
    result = judge.evaluate(JudgeInput(
        case_id="test_1",
        query="test",
        expected="blocked",
        actual="blocked",
        rubric="",
    ))
    assert result.score == 1.0
    assert result.passed is True
    assert result.judge_provider == "fake"


def test_fake_judge_mismatch():
    judge = FakeJudge()
    result = judge.evaluate(JudgeInput(
        case_id="test_2",
        query="test",
        expected="success",
        actual="failed",
        rubric="",
    ))
    assert result.score < 1.0
    assert result.passed is False


def test_fake_judge_blocked_like():
    judge = FakeJudge()
    result = judge.evaluate(JudgeInput(
        case_id="test_3",
        query="test",
        expected="blocked",
        actual="failed",
        rubric="",
    ))
    assert result.score == 0.8
    assert result.passed is True


def test_bad_case_runner_with_judge():
    runner = BadCaseRunner(judge=FakeJudge())
    summary = runner.run(use_judge=True, suite="security")
    assert summary.judge_average_score is not None
    assert summary.total >= 8


def test_llm_judge_provider_unavailable():
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(JudgeInput(
        case_id="test_llm",
        query="test",
        expected="success",
        actual="success",
        rubric="",
    ))
    assert result.judge_provider == "llm_unavailable"
    assert result.score == 0.0
    assert "unavailable" in result.reasoning.lower() or "not configured" in result.reasoning.lower()


def test_bad_case_runner_records_judge_metadata_tokens():
    class StubJudge:
        def evaluate(self, judge_input: JudgeInput) -> JudgeResult:
            return JudgeResult(
                score=0.7,
                passed=True,
                reasoning="stub judge",
                judge_provider="litellm",
                fallback_used=False,
                fallback_reason="",
                provider_metadata={"request_id": "judge-r1"},
                prompt_tokens=33,
                completion_tokens=17,
                cost=0.08,
                confidence=0.75,
            )

    recorder = RuntimeMetricsRecorder()
    runner = BadCaseRunner(metrics_recorder=recorder, judge=StubJudge())
    summary = runner.run(use_judge=True, suite="security", limit=1)
    assert summary.total == 1
    assert recorder.total_prompt_tokens == 33
    assert recorder.total_completion_tokens == 17
    assert recorder.total_cost == 0.08


def test_bad_cases_run_api():
    reset_runtime_for_test()
    resp = client.post("/eval/bad-cases/run", json={"use_judge": False, "suite": "security"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 8
    assert "accuracy" in data
    assert "failures" in data
    reset_runtime_for_test()


def test_bad_cases_run_api_total():
    reset_runtime_for_test()
    resp = client.post("/eval/bad-cases/run", json={"use_judge": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 30
    reset_runtime_for_test()


def test_bad_cases_list_api():
    resp = client.get("/eval/bad-cases")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 30


def test_bad_cases_list_api_suite_filter():
    resp = client.get("/eval/bad-cases", params={"suite": "security"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 8
    assert all(c["suite"] == "security" for c in data)


def test_eval_summary_contains_bad_case_count():
    reset_runtime_for_test()
    resp = client.get("/eval/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "bad_case_count" in data
    assert data["bad_case_count"] >= 30
    assert "bad_case_eval_available" in data
    assert data["bad_case_eval_available"] is True
    reset_runtime_for_test()


def test_metrics_after_badcase_run():
    recorder = RuntimeMetricsRecorder()
    runner = BadCaseRunner(metrics_recorder=recorder, judge=FakeJudge())
    runner.run(use_judge=True, suite="security")

    s = recorder.summary()
    assert s["task_count"] >= 8
    assert s["total_prompt_tokens"] == 0
    assert s["total_cost"] == 0.0


def test_bad_cases_run_api_with_judge():
    reset_runtime_for_test()
    resp = client.post("/eval/bad-cases/run", json={"use_judge": True, "suite": "security"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 8
    assert data["judge_average_score"] is not None
    reset_runtime_for_test()


def test_bad_cases_run_api_litellm_config_error_not_500(monkeypatch):
    monkeypatch.setattr(settings, "judge_provider", "litellm")
    monkeypatch.setattr(settings, "judge_fallback_to_fake", False)
    monkeypatch.setattr(settings, "llm_api_key", "")
    reset_runtime_for_test()
    resp = client.post("/eval/bad-cases/run", json={"use_judge": True, "suite": "security", "limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["judge_average_score"] is not None
    monkeypatch.setattr(settings, "judge_provider", "fake")
    monkeypatch.setattr(settings, "judge_fallback_to_fake", True)
    reset_runtime_for_test()


def test_bad_cases_run_api_request_override_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "judge_provider", "litellm")
    monkeypatch.setattr(settings, "judge_fallback_to_fake", False)
    reset_runtime_for_test()
    resp = client.post(
        "/eval/bad-cases/run",
        json={"use_judge": True, "suite": "security", "limit": 1, "judge_provider": "fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["judge_average_score"] is not None
    monkeypatch.setattr(settings, "judge_provider", "fake")
    monkeypatch.setattr(settings, "judge_fallback_to_fake", True)
    reset_runtime_for_test()


def test_bad_cases_run_api_request_override_litellm_unavailable_not_500(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    reset_runtime_for_test()
    resp = client.post(
        "/eval/bad-cases/run",
        json={
            "use_judge": True,
            "suite": "security",
            "limit": 1,
            "judge_provider": "litellm",
            "judge_fallback_to_fake": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["judge_average_score"] is not None
    reset_runtime_for_test()


def test_bad_cases_run_api_default_use_judge_false_still_works():
    reset_runtime_for_test()
    resp = client.post("/eval/bad-cases/run", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 30
    reset_runtime_for_test()
