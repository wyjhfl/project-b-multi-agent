from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.auth.oidc_config import (
    build_oidc_status,
    get_oidc_client_secret,
    map_oidc_roles,
    validate_oidc_settings,
)
from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.main import app


client = TestClient(app)


def _set_base_oidc(monkeypatch):
    monkeypatch.setattr(settings, "oidc_enabled", False)
    monkeypatch.setattr(settings, "oidc_issuer_url", "")
    monkeypatch.setattr(settings, "oidc_client_id", "")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "")
    monkeypatch.setattr(settings, "oidc_scopes", "openid,email,profile")
    monkeypatch.setattr(settings, "oidc_role_claim", "roles")
    monkeypatch.setattr(settings, "oidc_default_role", "viewer")
    monkeypatch.setattr(settings, "oidc_allowed_roles", "admin,operator,viewer,auditor")
    monkeypatch.setattr(settings, "oidc_require_https", True)


def _set_production_guard_defaults(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret", "very-strong-secret-32-bytes-production")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "rbac_enabled", True)
    monkeypatch.setattr(settings, "storage_backend", "sqlite")
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "redis_enabled", False)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "mcp_mode", "fake")
    monkeypatch.setattr(settings, "mcp_server_command_allowlist", "")
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "OPENAI_API_KEY")
    monkeypatch.setattr(settings, "cors_enabled", True)
    monkeypatch.setattr(settings, "cors_allow_origins", "https://console.example.com")
    monkeypatch.setattr(settings, "security_headers_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 1048576)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 120)
    monkeypatch.setattr(settings, "rate_limit_burst", 60)
    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    monkeypatch.setattr(settings, "log_redaction_enabled", True)
    monkeypatch.setattr(settings, "log_level", "INFO")
    monkeypatch.setattr(settings, "audit_retention_enabled", True)
    monkeypatch.setattr(settings, "audit_retention_days", 90)
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    monkeypatch.setattr(settings, "audit_export_max_rows", 1000)
    monkeypatch.setattr(settings, "audit_export_format", "jsonl")
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", True)


def test_oidc_status_when_disabled(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)

    status = build_oidc_status(settings)
    assert status["enabled"] is False
    assert status["client_secret_present"] is False
    assert status["client_secret_env"] == "OIDC_CLIENT_SECRET"
    assert isinstance(status["errors"], list)
    assert isinstance(status["warnings"], list)


def test_validate_oidc_enabled_missing_required_fields(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_client_secret_env", "MISSING_OIDC_SECRET")
    monkeypatch.delenv("MISSING_OIDC_SECRET", raising=False)

    result = validate_oidc_settings(settings)
    assert any("OIDC_ISSUER_URL" in msg for msg in result["errors"])
    assert any("OIDC_CLIENT_ID" in msg for msg in result["errors"])
    assert any("OIDC_REDIRECT_URI" in msg for msg in result["errors"])
    assert any("MISSING_OIDC_SECRET" in msg for msg in result["errors"])


def test_client_secret_presence_bool_and_no_leak(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_TEST")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_TEST", "very-secret-oidc-value")

    status = build_oidc_status(settings)
    dumped = str(status)
    assert status["client_secret_present"] is True
    assert "very-secret-oidc-value" not in dumped
    assert get_oidc_client_secret(settings) == "very-secret-oidc-value"


def test_production_require_https_rejects_http_urls(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "http://idp.example.com/realm/demo")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "http://console.example.com/callback")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_TEST")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_TEST", "oidc-secret")

    result = validate_oidc_settings(settings)
    assert any("OIDC_ISSUER_URL" in msg and "https" in msg for msg in result["errors"])
    assert any("OIDC_REDIRECT_URI" in msg and "https" in msg for msg in result["errors"])


def test_development_allow_localhost_http_with_warning(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "http://localhost:8080/realms/demo")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "http://localhost:3000/auth/callback")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_TEST")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_TEST", "oidc-secret")

    result = validate_oidc_settings(settings)
    assert result["errors"] == []
    assert any("development 环境允许" in msg for msg in result["warnings"])


def test_role_mapping_only_allows_known_roles(monkeypatch):
    _set_base_oidc(monkeypatch)
    claims = {"roles": ["admin", "unknown", "auditor"]}

    mapped = map_oidc_roles(claims, settings)
    assert mapped == ["admin", "auditor"]


def test_role_mapping_fallback_to_viewer(monkeypatch):
    _set_base_oidc(monkeypatch)
    claims = {"roles": ["unknown", "nobody"]}

    mapped = map_oidc_roles(claims, settings)
    assert mapped == ["viewer"]


def test_deployment_guard_production_oidc_disabled_not_block(monkeypatch):
    _set_production_guard_defaults(monkeypatch)
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", False)

    result = run_deployment_checks()
    assert result.ok is True
    assert any("oidc_enabled" in item for item in result.warnings)


def test_deployment_guard_production_oidc_enabled_missing_configs_block(monkeypatch):
    _set_production_guard_defaults(monkeypatch)
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_client_secret_env", "MISSING_OIDC_SECRET")
    monkeypatch.delenv("MISSING_OIDC_SECRET", raising=False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("oidc_issuer_url" in item for item in result.errors)
    assert any("oidc_client_id" in item for item in result.errors)
    assert any("oidc_redirect_uri" in item for item in result.errors)
    assert any("oidc_client_secret_present" in item for item in result.errors)


def test_oidc_status_api_returns_200_without_secret_leak(monkeypatch):
    _set_base_oidc(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://idp.example.com/realms/demo")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b-console")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://console.example.com/auth/callback")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_API_TEST")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_API_TEST", "api-secret-value")

    response = client.get("/auth/oidc/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["client_secret_present"] is True
    assert "api-secret-value" not in str(data)
