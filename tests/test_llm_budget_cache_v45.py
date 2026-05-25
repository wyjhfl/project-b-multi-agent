from __future__ import annotations

import json

from app.agent.nl2sql.provider import LLMGenerateMetadata, LLMProvider
from app.core.config import settings
from app.harness.eval.judge import JudgeInput, LLMJudgeProvider
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.harness.llm.budget import get_llm_budget_manager
from app.main import reset_runtime_for_test
from app.services.nl2sql_pipeline import NL2SQLPipeline


class _CountingProvider(LLMProvider):
    def __init__(self, *, score: float = 0.8) -> None:
        self.calls = 0
        self._score = score

    @property
    def name(self) -> str:
        return "litellm"

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return json.dumps(
            {
                "sql": "SELECT metric_date, gmv FROM daily_metrics",
                "confidence": self._score,
                "reasoning": "ok",
                "selected_tables": ["daily_metrics"],
            },
            ensure_ascii=False,
        )

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        return LLMGenerateMetadata(
            content=self.generate(prompt),
            provider="litellm",
            model="budget-cache-model",
            prompt_tokens=21,
            completion_tokens=9,
            total_tokens=30,
            cost=0.06,
            request_id="req-budget-cache",
            latency_ms=2.0,
            error_type=None,
        )


class _JudgeProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "litellm"

    def generate(self, prompt: str) -> str:
        return '{"score":0.9,"passed":true,"reasoning":"ok","confidence":0.9}'

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        return LLMGenerateMetadata(
            content=self.generate(prompt),
            provider="litellm",
            model="judge-budget-model",
            prompt_tokens=15,
            completion_tokens=5,
            total_tokens=20,
            cost=0.04,
            request_id="req-judge-budget",
            latency_ms=1.0,
            error_type=None,
        )


def _judge_input() -> JudgeInput:
    return JudgeInput(
        case_id="budget_case_001",
        query="今天GMV多少",
        expected="success",
        actual="success",
        rubric="",
    )


def test_budget_disabled_default_does_not_affect_fake_paths(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少", generator="mock")
    assert result["guard_allowed"] is True
    assert result["fallback_used"] is False

    judge = LLMJudgeProvider(provider="fake", fallback_to_fake=False)
    judge_result = judge.evaluate(_judge_input())
    assert judge_result.judge_provider == "fake"
    assert judge_result.passed is True


def test_nl2sql_budget_blocked_fallback_true(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    monkeypatch.setattr(settings, "llm_budget_soft_usd", 0.05)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    budget = get_llm_budget_manager()
    budget.record_usage("nl2sql", "litellm", "m", prompt_tokens=0, completion_tokens=0, cost=0.2)
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)

    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=True)
    assert result["generator_used"] == "mock_fallback"
    assert result["fallback_used"] is True
    assert "budget_blocked" in (result["fallback_reason"] or "")
    assert provider.calls == 0


def test_nl2sql_budget_blocked_no_fallback_and_no_execute(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    budget = get_llm_budget_manager()
    budget.record_usage("nl2sql", "litellm", "m", prompt_tokens=0, completion_tokens=0, cost=0.2)
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)

    pipeline = NL2SQLPipeline()
    result = pipeline.run("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert result["guard_allowed"] is False
    assert result["fallback_used"] is False
    assert "budget_blocked" in (result["fallback_reason"] or "")
    assert result["execution"]["success"] is False
    assert provider.calls == 0


def test_judge_budget_blocked_fallback_fake(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    reset_runtime_for_test()
    budget = get_llm_budget_manager()
    budget.record_usage("judge", "litellm", "j", prompt_tokens=0, completion_tokens=0, cost=0.2)

    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: _JudgeProvider())
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=True)
    result = judge.evaluate(_judge_input())
    assert result.judge_provider == "fallback_fake"
    assert result.fallback_used is True
    assert "budget_blocked" in result.fallback_reason


def test_judge_budget_blocked_no_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    reset_runtime_for_test()
    budget = get_llm_budget_manager()
    budget.record_usage("judge", "litellm", "j", prompt_tokens=0, completion_tokens=0, cost=0.2)

    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: _JudgeProvider())
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_judge_input())
    assert result.judge_provider == "llm_unavailable"
    assert result.fallback_used is False
    assert "budget_blocked" in result.fallback_reason


def test_nl2sql_success_records_usage(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 10.0)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    recorder = RuntimeMetricsRecorder()
    pipeline = NL2SQLPipeline()
    pipeline.set_metrics_recorder(recorder)
    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert result["guard_allowed"] is True
    assert provider.calls == 1
    assert recorder.total_prompt_tokens == 21
    assert recorder.total_completion_tokens == 9
    assert recorder.total_cost == 0.06

    budget_summary = get_llm_budget_manager().summary()
    assert budget_summary["current_cost"] >= 0.06
    assert budget_summary["by_provider"].get("litellm", 0.0) >= 0.06


def test_nl2sql_cache_enabled_second_call_hits_cache(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", True)
    monkeypatch.setattr(settings, "llm_cache_ttl_seconds", 3600)
    reset_runtime_for_test()

    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    recorder = RuntimeMetricsRecorder()
    pipeline = NL2SQLPipeline()
    pipeline.set_metrics_recorder(recorder)

    first = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    second = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert first["guard_allowed"] is True
    assert second["guard_allowed"] is True
    assert provider.calls == 1
    assert any("cache_hit:nl2sql" in w for w in second["warnings"])
    assert recorder.summary()["cache_hit_count"] >= 1


def test_nl2sql_cache_disabled_calls_provider_every_time(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    pipeline = NL2SQLPipeline()
    pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert provider.calls == 2
