from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.nl2sql.provider import create_provider
from app.core.config import settings
from app.harness.llm.pilot_smoke_report import build_nl2sql_pilot_case, write_pilot_report_for_case
from app.main import app


client = TestClient(app)


def _is_real_llm_opt_in_enabled() -> tuple[bool, str]:
    required = [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    ]
    missing = [name for name in required if os.getenv(name, "").strip().lower() != "true"]
    if missing:
        return False, f"real llm smoke not enabled: {', '.join(missing)}"
    return True, ""


def _apply_real_llm_env_to_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    model = os.getenv("REAL_LLM_MODEL", "").strip()
    base_url = os.getenv("REAL_LLM_BASE_URL", "").strip()
    api_key_env_name = os.getenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env_name, "")
    monkeypatch.setattr(settings, "llm_provider", "litellm")
    monkeypatch.setattr(settings, "llm_model", model)
    monkeypatch.setattr(settings, "llm_base_url", base_url)
    monkeypatch.setattr(settings, "llm_api_key", api_key)


@pytest.mark.real_llm
def test_real_llm_preflight_network_check_opt_in_only(monkeypatch: pytest.MonkeyPatch):
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)
    _apply_real_llm_env_to_runtime_settings(monkeypatch)

    response = client.get("/llm/preflight", params={"network_check": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"passed", "failed"}
    assert "checks" in payload
    assert isinstance(payload["checks"], list)


@pytest.mark.real_llm
def test_real_llm_provider_minimal_call_opt_in_only(monkeypatch: pytest.MonkeyPatch):
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)
    _apply_real_llm_env_to_runtime_settings(monkeypatch)

    provider = create_provider(
        "litellm",
        api_key=os.getenv(os.getenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY"), ""),
        model=os.getenv("REAL_LLM_MODEL", ""),
        base_url=os.getenv("REAL_LLM_BASE_URL", ""),
    )
    metadata = provider.generate_with_metadata("请只回复 ok")
    assert isinstance(metadata.content, str)
    assert len(metadata.content.strip()) > 0
    assert metadata.provider == "litellm"
    print(
        "[real_llm_smoke] provider_call "
        f"provider={metadata.provider} model={metadata.model} latency_ms={metadata.latency_ms} "
        f"prompt_tokens={metadata.prompt_tokens} completion_tokens={metadata.completion_tokens} "
        f"total_tokens={metadata.total_tokens} cost={metadata.cost} request_id={metadata.request_id}"
    )


@pytest.mark.real_llm
def test_real_llm_nl2sql_preview_opt_in_only(monkeypatch: pytest.MonkeyPatch):
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)
    _apply_real_llm_env_to_runtime_settings(monkeypatch)

    response = client.post(
        "/nl2sql/preview",
        json={
            "query": "今天GMV多少",
            "generator": "llm",
            "provider": "litellm",
            "fallback_to_mock": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    report_paths = write_pilot_report_for_case(
        build_nl2sql_pilot_case(payload),
        report_prefix="real-llm-smoke-nl2sql",
    )
    assert Path(report_paths["json_path"]).exists()
    assert Path(report_paths["markdown_path"]).exists()

    summary = payload.get("acceptance_summary") or {}
    if payload.get("generator_used") == "llm" and payload.get("provider_used") == "litellm":
        provider_metadata = payload.get("provider_metadata") or {}
        assert "latency_ms" in provider_metadata
        assert "prompt_tokens" in provider_metadata
        assert "completion_tokens" in provider_metadata
        assert "total_tokens" in provider_metadata
        assert "cost" in provider_metadata
        assert summary.get("request_id", "") != ""
        print(
            "[real_llm_smoke] nl2sql_preview "
            f"generator_used={payload.get('generator_used')} provider_used={payload.get('provider_used')} "
            f"fallback_used={payload.get('fallback_used')} fallback_reason={payload.get('fallback_reason', '')} "
            f"budget_action={summary.get('budget_action','')} cache_hit={summary.get('cache_hit')} "
            f"latency_ms={provider_metadata.get('latency_ms')} prompt_tokens={provider_metadata.get('prompt_tokens')} "
            f"completion_tokens={provider_metadata.get('completion_tokens')} total_tokens={provider_metadata.get('total_tokens')} "
            f"cost={provider_metadata.get('cost')} request_id={provider_metadata.get('request_id')} "
            f"report_json={report_paths['json_path']} report_md={report_paths['markdown_path']}"
        )
    else:
        assert payload.get("fallback_used") is True
        assert isinstance(payload.get("fallback_reason"), str)
        assert payload.get("fallback_reason", "").strip() != ""
        assert payload.get("generator_used") == "mock_fallback"
        assert summary.get("fallback_reason", "") != ""
        print(
            "[real_llm_smoke] nl2sql_preview "
            f"generator_used={payload.get('generator_used')} provider_used={payload.get('provider_used')} "
            f"fallback_used={payload.get('fallback_used')} fallback_reason={payload.get('fallback_reason', '')} "
            f"budget_action={summary.get('budget_action','')} cache_hit={summary.get('cache_hit')} request_id={summary.get('request_id','')} "
            f"report_json={report_paths['json_path']} report_md={report_paths['markdown_path']}"
        )


def test_real_llm_smoke_offline_fallback_path_still_available():
    response = client.post(
        "/nl2sql/preview",
        json={
            "query": "今天GMV多少",
            "generator": "llm",
            "provider": "litellm",
            "fallback_to_mock": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["generator_used"] in {"llm", "mock_fallback"}


def test_real_llm_smoke_report_generation_with_tmp_dir(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("REAL_LLM_PILOT_COMMIT", "commit-v92")
    payload = {
        "generator_used": "mock_fallback",
        "provider_used": "litellm",
        "fallback_used": True,
        "fallback_reason": "budget_blocked",
        "guard_allowed": True,
        "warnings": ["cache_hit:nl2sql"],
        "provider_metadata": {
            "request_id": "req-v92",
            "latency_ms": 12.5,
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
            "cost": 0.18,
            "authorization_header": "Bearer secret",
            "database_url": "postgresql://user:dbpassword@localhost:5432/db",
        },
        "acceptance_summary": {
            "provider": "litellm",
            "model": "gpt-4o-mini",
            "request_id": "req-v92",
            "real_call_attempted": True,
            "real_call_succeeded": False,
            "fallback_used": True,
            "fallback_reason": "budget_blocked",
            "budget_action": "fallback",
            "cache_hit": True,
            "latency_ms": 12.5,
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
            "cost": 0.18,
            "error_type": "budget_block",
        },
    }
    report_paths = write_pilot_report_for_case(
        build_nl2sql_pilot_case(payload),
        report_prefix="unit-nl2sql",
    )
    json_text = Path(report_paths["json_path"]).read_text(encoding="utf-8")
    md_text = Path(report_paths["markdown_path"]).read_text(encoding="utf-8")
    assert str(tmp_path) in report_paths["json_path"]
    assert '"prompt_tokens": 20' in json_text
    assert "tokens(prompt/completion/total): 20/8/28" in md_text
    assert "budget_blocked" in json_text
    assert "req-v92" in md_text
    assert "Bearer secret" not in json_text
    assert "dbpassword" not in json_text
    assert "sk-test-key" not in json_text
    assert '"audit_event_id"' in json_text
    assert '"runtime_metric_keys"' in json_text
