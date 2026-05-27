from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.agent.nl2sql.provider import ProviderConfigError
from app.core.config import settings
from app.harness.eval.judge import JudgeInput, LLMJudgeProvider
from app.harness.llm.pilot_smoke_report import build_judge_pilot_case, write_pilot_report_for_case


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

    report_paths = write_pilot_report_for_case(
        build_judge_pilot_case(result),
        report_prefix="real-llm-smoke-judge",
    )
    assert Path(report_paths["json_path"]).exists()
    assert Path(report_paths["markdown_path"]).exists()

    summary = (result.provider_metadata or {}).get("acceptance_summary") or {}
    if result.judge_provider == "litellm":
        provider_metadata = result.provider_metadata or {}
        assert "latency_ms" in provider_metadata
        assert "prompt_tokens" in provider_metadata
        assert "completion_tokens" in provider_metadata
        assert "total_tokens" in provider_metadata
        assert "cost" in provider_metadata
        assert summary.get("request_id", "") != ""
        print(
            "[real_llm_smoke] judge "
            f"judge_provider={result.judge_provider} score={result.score} passed={result.passed} "
            f"confidence={result.confidence} fallback_used={result.fallback_used} "
            f"fallback_reason={result.fallback_reason} budget_action={summary.get('budget_action','')} "
            f"cache_hit={summary.get('cache_hit')} latency_ms={provider_metadata.get('latency_ms')} "
            f"prompt_tokens={provider_metadata.get('prompt_tokens')} completion_tokens={provider_metadata.get('completion_tokens')} "
            f"total_tokens={provider_metadata.get('total_tokens')} cost={provider_metadata.get('cost')} "
            f"request_id={provider_metadata.get('request_id')} error_type={provider_metadata.get('error_type')} "
            f"report_json={report_paths['json_path']} report_md={report_paths['markdown_path']}"
        )
    else:
        assert result.fallback_used is True
        assert isinstance(result.fallback_reason, str)
        assert result.fallback_reason.strip() != ""
        assert summary.get("fallback_reason", "") != ""
        print(
            "[real_llm_smoke] judge "
            f"judge_provider={result.judge_provider} score={result.score} passed={result.passed} "
            f"confidence={result.confidence} fallback_used={result.fallback_used} "
            f"fallback_reason={result.fallback_reason} budget_action={summary.get('budget_action','')} "
            f"cache_hit={summary.get('cache_hit')} request_id={summary.get('request_id','')} "
            f"report_json={report_paths['json_path']} report_md={report_paths['markdown_path']}"
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
    summary = (result.provider_metadata or {}).get("acceptance_summary") or {}
    assert summary.get("error_type", "") != ""


def test_real_llm_judge_report_generation_with_tmp_dir(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

    class _DummyResult:
        judge_provider = "fallback_fake"
        score = 0.8
        passed = True
        confidence = 0.75
        fallback_used = True
        fallback_reason = "budget_blocked"
        provider_metadata = {
            "acceptance_summary": {
                "provider": "litellm",
                "model": "gpt-4o-mini",
                "request_id": "judge-req",
                "real_call_attempted": True,
                "real_call_succeeded": False,
                "fallback_used": True,
                "fallback_reason": "budget_blocked",
                "budget_action": "fallback",
                "cache_hit": False,
                "latency_ms": 9.8,
                "prompt_tokens": 11,
                "completion_tokens": 6,
                "total_tokens": 17,
                "cost": 0.07,
                "error_type": "budget_block",
            },
            "database_password": "db-password-value",
            "session_cookie": "sid=abc",
            "redis_url": "redis://:redispassword@localhost:6379/0",
        }

    report_paths = write_pilot_report_for_case(
        build_judge_pilot_case(_DummyResult()),
        report_prefix="unit-judge",
    )
    json_text = Path(report_paths["json_path"]).read_text(encoding="utf-8")
    md_text = Path(report_paths["markdown_path"]).read_text(encoding="utf-8")

    assert str(tmp_path) in report_paths["json_path"]
    assert '"prompt_tokens": 11' in json_text
    assert "tokens(prompt/completion/total): 11/6/17" in md_text
    assert "judge-req" in md_text
    assert "db-password-value" not in json_text
    assert "sid=abc" not in json_text
    assert "redispassword" not in json_text
    assert "sk-test-key" not in json_text
