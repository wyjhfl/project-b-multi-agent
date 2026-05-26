from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.main import app


client = TestClient(app)


def test_development_mode_warn_only(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    result = run_deployment_checks()
    assert result.ok is True
    assert result.environment == "development"
    assert result.errors == []
    assert len(result.warnings) >= 1


def test_production_mode_required_fields(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-change-me-please-32-bytes")
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "mcp_mode", "real")
    monkeypatch.setattr(settings, "mcp_server_command_allowlist", "")
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "MISSING_REAL_LLM_KEY_ENV")
    monkeypatch.delenv("MISSING_REAL_LLM_KEY_ENV", raising=False)

    result = run_deployment_checks()
    assert result.ok is False
    assert result.environment == "production"
    assert any("jwt_secret" in item for item in result.errors)
    assert any("auth_enabled" in item for item in result.errors)
    assert any("rbac_enabled" in item for item in result.errors)
    assert any("database_url" in item for item in result.errors)
    assert any("redis_url" in item for item in result.errors)
    assert any("mcp_server_command_allowlist" in item for item in result.errors)
    assert any("real_llm_model" in item for item in result.errors)
    assert any("real_llm_api_key_present" in item for item in result.errors)


def test_production_mode_pass_without_secret_leak(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret", "very-strong-secret-32-bytes-production")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "rbac_enabled", True)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:password@db:5432/project_b")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")
    monkeypatch.setattr(settings, "mcp_mode", "fake")
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)

    result = run_deployment_checks()
    payload = result.model_dump_json()
    assert result.ok is True
    assert "very-strong-secret-32-bytes-production" not in payload
    assert "password@db" not in payload


def test_deployment_check_api_always_200(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-change-me-please-32-bytes")
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "")

    response = client.get("/deployment/check")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert isinstance(data["errors"], list)

