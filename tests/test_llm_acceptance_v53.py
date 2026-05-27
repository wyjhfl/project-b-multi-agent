from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agent.nl2sql.provider import LLMGenerateMetadata, LLMProvider
from app.core.config import settings
from app.harness.llm import summarize_llm_acceptance
from app.main import app
from app.main import reset_runtime_for_test
from app.services.nl2sql_pipeline import NL2SQLPipeline

client = TestClient(app)


class _CountingProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "litellm"

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return json.dumps(
            {
                "sql": "SELECT metric_date, gmv FROM daily_metrics",
                "confidence": 0.9,
                "reasoning": "ok",
                "selected_tables": ["daily_metrics"],
            },
            ensure_ascii=False,
        )

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        return LLMGenerateMetadata(
            content=self.generate(prompt),
            provider="litellm",
            model="acceptance-model",
            prompt_tokens=30,
            completion_tokens=12,
            total_tokens=42,
            cost=0.21,
            request_id="req-v53",
            latency_ms=6.2,
            error_type=None,
        )


def test_acceptance_summary_collects_token_cost_metadata():
    metadata = LLMGenerateMetadata(
        content="ok",
        provider="litellm",
        model="m",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=0.01,
        request_id="x",
        latency_ms=3.0,
        error_type=None,
    )
    result = summarize_llm_acceptance(
        mode="provider",
        provider="litellm",
        model="m",
        provider_metadata=metadata.to_dict(),
    )
    payload = result.to_dict()
    assert payload["prompt_tokens"] == 10
    assert payload["completion_tokens"] == 5
    assert payload["total_tokens"] == 15
    assert payload["cost"] == 0.01
    assert payload["real_call_attempted"] is True
    assert payload["request_id"] == "x"


def test_acceptance_summary_fallback_reason_non_empty():
    result = summarize_llm_acceptance(
        mode="nl2sql",
        provider="litellm",
        model="m",
        fallback_used=True,
        fallback_reason="",
        error_type="ProviderTimeoutError",
        budget_status={"action": "fallback"},
    )
    payload = result.to_dict()
    assert payload["fallback_used"] is True
    assert payload["fallback_reason"] != ""


def test_budget_disabled_does_not_block_llm_path(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)

    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    summary = result.get("acceptance_summary") or {}
    assert result["guard_allowed"] is True
    assert provider.calls == 1
    assert (result.get("budget_status") or {}).get("reason") == "budget_disabled"
    assert summary.get("provider") == "litellm"
    assert summary.get("real_call_attempted") is True
    assert summary.get("real_call_succeeded") is True
    assert summary.get("cache_hit") is False
    assert summary.get("request_id") == "req-v53"


def test_budget_hard_limit_with_fallback_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    pipeline = NL2SQLPipeline()
    pipeline._budget_manager.record_usage("nl2sql", "litellm", "acceptance-model", 0, 0, 0.2)

    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=True)
    summary = result.get("acceptance_summary") or {}
    assert result["generator_used"] == "mock_fallback"
    assert result["fallback_used"] is True
    assert (result["fallback_reason"] or "").strip() != ""
    assert "budget_blocked" in result["fallback_reason"]
    assert provider.calls == 0
    assert summary.get("fallback_used") is True
    assert summary.get("fallback_reason") != ""
    assert summary.get("budget_action") == "fallback"


def test_budget_hard_limit_without_fallback_fails_and_no_execute(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.1)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    pipeline = NL2SQLPipeline()
    pipeline._budget_manager.record_usage("nl2sql", "litellm", "acceptance-model", 0, 0, 0.2)

    called = {"execute": 0}

    class _NeverExecutor:
        def execute(self, sql: str):
            called["execute"] += 1
            raise AssertionError("预算阻断后不应执行 SQL")

    monkeypatch.setattr("app.services.nl2sql_pipeline.SQLiteReadOnlyExecutor", _NeverExecutor)
    result = pipeline.run("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    summary = result.get("acceptance_summary") or {}
    assert result["guard_allowed"] is False
    assert result["fallback_used"] is False
    assert (result["fallback_reason"] or "").strip() != ""
    assert "budget_blocked" in result["fallback_reason"]
    assert called["execute"] == 0
    assert provider.calls == 0
    assert summary.get("budget_action") == "fallback"
    assert summary.get("error_type") == "budget_blocked"


def test_cache_hit_semantics_on_second_request(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", True)
    monkeypatch.setattr(settings, "llm_cache_ttl_seconds", 3600)
    reset_runtime_for_test()
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)
    pipeline = NL2SQLPipeline()

    first = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    second = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    first_summary = first.get("acceptance_summary") or {}
    second_summary = second.get("acceptance_summary") or {}
    assert first["guard_allowed"] is True
    assert second["guard_allowed"] is True
    assert provider.calls == 1
    assert any("cache_hit:nl2sql" in w for w in second["warnings"])
    assert (second.get("provider_metadata") or {}).get("cache_hit") is True
    assert second_summary.get("cache_hit") is True
    assert second_summary.get("real_call_attempted") is False
    assert second_summary.get("fallback_reason") == ""
    assert first_summary.get("request_id") == "req-v53"


def test_fallback_reason_observable_when_provider_invalid(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少", generator="llm", provider="unknown", fallback_to_mock=False)
    summary = result.get("acceptance_summary") or {}
    assert result["guard_allowed"] is False
    assert (result["fallback_reason"] or "").strip() != ""
    assert summary.get("fallback_reason") != ""


def test_metrics_runtime_contains_llm_budget_cache_summary(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 1.0)
    monkeypatch.setattr(settings, "llm_cache_enabled", True)
    reset_runtime_for_test()

    response = client.get("/metrics/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert "llm_budget" in payload
    assert "llm_cache" in payload
    assert "enabled" in payload["llm_budget"]
    assert "enabled" in payload["llm_cache"]


def test_nl2sql_preview_should_expose_evidence_links(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", False)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    reset_runtime_for_test()

    provider = _CountingProvider()
    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda *_args, **_kwargs: provider)

    response = client.post(
        "/nl2sql/preview",
        json={
            "query": "今天GMV多少",
            "generator": "llm",
            "provider": "litellm",
            "fallback_to_mock": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    links = payload.get("evidence_links") or {}
    assert links.get("audit_event_id", "").startswith("aud_")
    assert links.get("audit_event_type") == "llm_acceptance"
    assert links.get("log_request_id") == "req-v53"
