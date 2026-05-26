from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.core.config import settings
from app.harness.llm import preflight as preflight_mod
from app.harness.llm.preflight import run_llm_provider_preflight
from app.main import app


client = TestClient(app)


def _set_default_real_llm_flags(monkeypatch):
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", False)
    monkeypatch.setattr(settings, "real_llm_provider", "litellm")
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "OPENAI_API_KEY")
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", False)
    monkeypatch.setattr(settings, "real_llm_preflight_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 15.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    monkeypatch.setattr(settings, "llm_retry_backoff_seconds", 0.5)


def test_preflight_default_disabled_no_network(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    called = {"count": 0}

    def _fake_network(*args, **kwargs):
        called["count"] += 1
        return True, "ok", 1.0

    monkeypatch.setattr(preflight_mod, "_perform_network_check", _fake_network)
    result = run_llm_provider_preflight(perform_network_check=True)
    assert result.status == "disabled"
    assert result.network_check_enabled is False
    assert called["count"] == 0


def test_preflight_missing_model_returns_structured_error(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "")
    result = run_llm_provider_preflight(perform_network_check=False)
    assert result.status == "failed"
    assert any("real_llm_model is empty" in err for err in result.errors)


def test_preflight_missing_api_key_env_no_leak(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-abc123")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_llm_provider_preflight(perform_network_check=False)
    text = str(result.to_dict())
    assert result.status == "failed"
    assert any("missing api key env: OPENAI_API_KEY" in err for err in result.errors)
    assert "sk-secret-abc123" not in text


def test_preflight_network_check_true_but_not_allowed(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-check")
    called = {"count": 0}

    def _fake_network(*args, **kwargs):
        called["count"] += 1
        return True, "ok", 1.0

    monkeypatch.setattr(preflight_mod, "_perform_network_check", _fake_network)
    result = run_llm_provider_preflight(perform_network_check=True)
    assert result.network_check_enabled is False
    assert called["count"] == 0


def test_preflight_config_complete_without_network_call(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-check")
    called = {"count": 0}

    def _fake_network(*args, **kwargs):
        called["count"] += 1
        return True, "ok", 1.0

    monkeypatch.setattr(preflight_mod, "_perform_network_check", _fake_network)
    result = run_llm_provider_preflight(perform_network_check=False)
    assert result.status in {"ready", "passed"}
    assert called["count"] == 0


def test_preflight_api_not_500_when_config_missing(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", False)
    response = client.get("/llm/preflight")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"disabled", "failed", "ready", "passed"}


def test_preflight_api_network_check_without_permission_no_network(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo")
    called = {"count": 0}

    def _fake_network(*args, **kwargs):
        called["count"] += 1
        return True, "ok", 1.0

    monkeypatch.setattr(preflight_mod, "_perform_network_check", _fake_network)
    response = client.get("/llm/preflight", params={"network_check": "true"})
    assert response.status_code == 200
    assert called["count"] == 0
