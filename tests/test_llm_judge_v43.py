from __future__ import annotations

import json

from app.agent.nl2sql.provider import LLMGenerateMetadata, LLMProvider, ProviderConfigError
from app.core.config import settings
from app.harness.eval.judge import JudgeInput, LLMJudgeProvider


def _build_input() -> JudgeInput:
    return JudgeInput(
        case_id="judge_case_001",
        query="今天GMV是多少",
        expected="success",
        actual="success",
        rubric="需要判断是否成功",
    )


class _ProviderWithContent(LLMProvider):
    def __init__(self, content: str) -> None:
        self._content = content

    @property
    def name(self) -> str:
        return "litellm"

    def generate(self, prompt: str) -> str:
        return self._content

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        return LLMGenerateMetadata(
            content=self._content,
            provider="litellm",
            model="judge-model",
            prompt_tokens=12,
            completion_tokens=8,
            total_tokens=20,
            cost=0.03,
            request_id="judge-req-1",
            latency_ms=5.0,
            error_type=None,
        )


def test_llm_judge_provider_parse_json_success(monkeypatch):
    provider = _ProviderWithContent(
        json.dumps(
            {
                "score": 0.9,
                "passed": True,
                "reasoning": "结果一致",
                "confidence": 0.88,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: provider)
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_build_input())
    assert result.judge_provider == "litellm"
    assert result.fallback_used is False
    assert result.score == 0.9
    assert result.passed is True
    assert result.confidence == 0.88
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert result.cost == 0.03


def test_llm_judge_provider_non_json_fallback_fake(monkeypatch):
    provider = _ProviderWithContent("not-json")
    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: provider)
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=True)
    result = judge.evaluate(_build_input())
    assert result.judge_provider == "fallback_fake"
    assert result.fallback_used is True
    assert "invalid" in result.fallback_reason.lower() or "json" in result.fallback_reason.lower()


def test_llm_judge_provider_json_not_object_fallback_fake(monkeypatch):
    provider = _ProviderWithContent(json.dumps(["bad-shape"], ensure_ascii=False))
    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: provider)
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=True)
    result = judge.evaluate(_build_input())
    assert result.judge_provider == "fallback_fake"
    assert result.fallback_used is True
    assert "object" in result.fallback_reason.lower()


def test_llm_judge_provider_score_confidence_clamped(monkeypatch):
    provider = _ProviderWithContent(
        json.dumps(
            {
                "score": 3.2,
                "passed": "true",
                "reasoning": "越界测试",
                "confidence": -5,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("app.harness.eval.judge.create_provider", lambda *_args, **_kwargs: provider)
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_build_input())
    assert result.score == 1.0
    assert result.confidence == 0.0
    assert result.passed is True


def test_llm_judge_provider_config_error_no_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.harness.eval.judge.create_provider",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ProviderConfigError("missing key")),
    )
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_build_input())
    assert result.judge_provider == "llm_unavailable"
    assert result.fallback_used is False
    assert "missing key" in result.fallback_reason


def test_llm_judge_provider_uses_judge_specific_overrides(monkeypatch):
    captured: dict[str, object] = {}

    class DummyProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "litellm"

        def generate(self, prompt: str) -> str:
            return '{"score":1,"passed":true,"reasoning":"ok","confidence":1}'

        def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
            return LLMGenerateMetadata(
                content=self.generate(prompt),
                provider="litellm",
                model="judge-model",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost=0.0,
                request_id="x",
                latency_ms=1.0,
                error_type=None,
            )

    def fake_create_provider(provider_name: str | None = None, **kwargs):
        captured["provider_name"] = provider_name
        captured.update(kwargs)
        return DummyProvider()

    monkeypatch.setattr(settings, "judge_model", "judge-special-model")
    monkeypatch.setattr(settings, "judge_timeout_seconds", 21.5)
    monkeypatch.setattr(settings, "judge_max_retries", 3)
    monkeypatch.setattr(settings, "judge_retry_backoff_seconds", 1.25)
    monkeypatch.setattr(settings, "llm_model", "nl2sql-model-should-not-be-used")
    monkeypatch.setattr("app.harness.eval.judge.create_provider", fake_create_provider)

    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_build_input())
    assert result.judge_provider == "litellm"
    assert captured["provider_name"] == "litellm"
    assert captured["model"] == "judge-special-model"
    assert captured["timeout_seconds"] == 21.5
    assert captured["max_retries"] == 3
    assert captured["retry_backoff_seconds"] == 1.25
