from __future__ import annotations

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
    monkeypatch.setattr(settings, "real_llm_base_url", "")
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
    assert result.allowed is False
    assert result.network_check_executed is False
    assert result.network_check_allowed is False
    assert all("real_llm_model is empty" not in err for err in result.errors)
    assert all("missing api key env" not in err for err in result.errors)
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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_llm_provider_preflight(perform_network_check=False)
    text = str(result.to_dict())
    assert result.status == "failed"
    assert any("missing api key env: OPENAI_API_KEY" in err for err in result.errors)
    assert "sk-" not in text


def test_preflight_enabled_unsupported_provider_returns_error(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_provider", "unsupported_provider")
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-check")

    result = run_llm_provider_preflight(perform_network_check=False)
    assert result.status == "failed"
    assert any("unsupported provider" in err for err in result.errors)


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
    assert result.network_check_executed is False
    assert any("network_check_not_allowed" in err for err in result.errors)
    assert "sk-real-check" not in str(result.to_dict())
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
    assert result.api_key_present is True
    assert result.network_check_allowed is True
    assert called["count"] == 0


def test_preflight_api_not_500_when_config_missing(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
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
    payload = response.json()
    assert payload["network_check_executed"] is False
    assert called["count"] == 0


def test_preflight_network_check_passes_base_url_to_create_provider(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_base_url", "https://mock-llm.local/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo")
    captured: dict[str, str] = {}

    class _Provider:
        def generate_with_metadata(self, prompt: str):
            class _Meta:
                content = "ok"
                latency_ms = 12.3

            return _Meta()

    def _fake_create_provider(**kwargs):
        captured["base_url"] = kwargs.get("base_url", "")
        return _Provider()

    monkeypatch.setattr(preflight_mod, "create_provider", _fake_create_provider)
    result = run_llm_provider_preflight(perform_network_check=True)
    assert result.status == "passed"
    assert result.base_url == "https://mock-llm.local/v1"
    assert captured.get("base_url") == "https://mock-llm.local/v1"


def test_preflight_latency_not_double_count_network_latency(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_network_check", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo")

    def _fake_network(*args, **kwargs):
        return True, "network_check_ok", 500.0

    monkeypatch.setattr(preflight_mod, "_perform_network_check", _fake_network)
    result = run_llm_provider_preflight(perform_network_check=True)
    assert result.latency_ms == 500.0


def test_preflight_base_url_redacted(monkeypatch):
    _set_default_real_llm_flags(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_preflight_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_base_url", "https://user:pass@example.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo")
    result = run_llm_provider_preflight(perform_network_check=False)
    assert "pass" not in result.base_url
    assert "***" in result.base_url
