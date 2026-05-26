from __future__ import annotations

import os

import pytest

from app.agent.nl2sql.provider import ProviderConfigError
from app.core.config import settings
from app.harness.eval.judge import JudgeInput, LLMJudgeProvider


def _is_real_llm_opt_in_enabled() -> tuple[bool, str]:
    required = [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    ]
    missing = [name for name in required if os.getenv(name, "").strip().lower() != "true"]
    if missing:
        return False, f"real llm judge smoke not enabled: {', '.join(missing)}"
    return True, ""


def _apply_real_llm_env_to_judge_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    model = os.getenv("REAL_LLM_MODEL", "").strip()
    base_url = os.getenv("REAL_LLM_BASE_URL", "").strip()
    api_key_env_name = os.getenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env_name, "")
    monkeypatch.setattr(settings, "judge_provider", "litellm")
    monkeypatch.setattr(settings, "judge_model", model)
    monkeypatch.setattr(settings, "judge_base_url", base_url)
    monkeypatch.setattr(settings, "llm_api_key", api_key)


def _build_smoke_input() -> JudgeInput:
    return JudgeInput(
        case_id="judge-smoke-001",
        query="今天GMV多少",
        expected="success",
        actual="success",
        rubric="actual 与 expected 语义一致即可",
    )


@pytest.mark.real_llm
def test_real_llm_judge_smoke_opt_in_only(monkeypatch: pytest.MonkeyPatch):
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)
    _apply_real_llm_env_to_judge_settings(monkeypatch)
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=True)
    result = judge.evaluate(_build_smoke_input())

    if result.judge_provider == "litellm":
        provider_metadata = result.provider_metadata or {}
        assert "latency_ms" in provider_metadata
        assert "prompt_tokens" in provider_metadata
        assert "completion_tokens" in provider_metadata
        assert "total_tokens" in provider_metadata
        assert "cost" in provider_metadata
        print(
            "[real_llm_smoke] judge "
            f"judge_provider={result.judge_provider} score={result.score} passed={result.passed} "
            f"confidence={result.confidence} fallback_used={result.fallback_used} "
            f"fallback_reason={result.fallback_reason} latency_ms={provider_metadata.get('latency_ms')} "
            f"prompt_tokens={provider_metadata.get('prompt_tokens')} completion_tokens={provider_metadata.get('completion_tokens')} "
            f"total_tokens={provider_metadata.get('total_tokens')} cost={provider_metadata.get('cost')} "
            f"request_id={provider_metadata.get('request_id')} error_type={provider_metadata.get('error_type')}"
        )
    else:
        assert result.fallback_used is True
        assert isinstance(result.fallback_reason, str)
        assert result.fallback_reason.strip() != ""
        print(
            "[real_llm_smoke] judge "
            f"judge_provider={result.judge_provider} score={result.score} passed={result.passed} "
            f"confidence={result.confidence} fallback_used={result.fallback_used} "
            f"fallback_reason={result.fallback_reason}"
        )


def test_real_llm_judge_smoke_fallback_disabled_returns_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.harness.eval.judge.create_provider",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ProviderConfigError("missing key")),
    )
    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=False)
    result = judge.evaluate(_build_smoke_input())
    assert result.judge_provider == "llm_unavailable"
    assert result.fallback_used is False
    assert result.fallback_reason.strip() != ""
