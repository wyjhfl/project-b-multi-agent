from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.nl2sql.provider import create_provider
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


@pytest.mark.real_llm
def test_real_llm_preflight_network_check_opt_in_only():
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)

    response = client.get("/llm/preflight", params={"network_check": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"passed", "failed"}
    assert "checks" in payload
    assert isinstance(payload["checks"], list)


@pytest.mark.real_llm
def test_real_llm_provider_minimal_call_opt_in_only():
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)

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
def test_real_llm_nl2sql_preview_opt_in_only():
    enabled, reason = _is_real_llm_opt_in_enabled()
    if not enabled:
        pytest.skip(reason)

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
    assert "generator_used" in payload
    assert "provider_used" in payload
    assert "guard_allowed" in payload


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
