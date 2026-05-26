from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.nl2sql.provider import create_provider
from app.core.config import settings
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
    if payload.get("generator_used") == "llm" or payload.get("provider_used") == "litellm":
        assert payload.get("generator_used") == "llm"
        assert payload.get("provider_used") == "litellm"
    else:
        assert payload.get("fallback_used") is True
        assert isinstance(payload.get("fallback_reason"), str)
        assert payload.get("fallback_reason", "").strip() != ""


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
