from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.main import app


client = TestClient(app)


def _set_production_secure_defaults(monkeypatch):
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
    monkeypatch.setattr(settings, "mcp_tool_allowlist", "")
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "OPENAI_API_KEY")
    monkeypatch.setattr(settings, "cors_enabled", True)
    monkeypatch.setattr(settings, "cors_allow_origins", "https://console.example.com")
    monkeypatch.setattr(settings, "security_headers_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 1048576)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
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
    monkeypatch.setattr(settings, "mcp_tool_allowlist", "")
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "MISSING_REAL_LLM_KEY_ENV")
    monkeypatch.setattr(settings, "cors_enabled", True)
    monkeypatch.setattr(settings, "cors_allow_origins", "")
    monkeypatch.setattr(settings, "security_headers_enabled", False)
    monkeypatch.setattr(settings, "request_size_limit_enabled", False)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 0)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_backend", "invalid")
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    monkeypatch.setattr(settings, "rate_limit_burst", -1)
    monkeypatch.setattr(settings, "structured_logging_enabled", False)
    monkeypatch.setattr(settings, "log_redaction_enabled", False)
    monkeypatch.setattr(settings, "log_level", "DEBUG")
    monkeypatch.setattr(settings, "audit_retention_enabled", False)
    monkeypatch.setattr(settings, "audit_retention_days", 0)
    monkeypatch.setattr(settings, "audit_export_max_rows", 20000)
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", False)
    monkeypatch.delenv("MISSING_REAL_LLM_KEY_ENV", raising=False)

    result = run_deployment_checks()
    assert result.ok is False
    assert result.environment == "production"
    assert any("jwt_secret" in item for item in result.errors)
    assert any("auth_enabled" in item for item in result.errors)
    assert any("rbac_enabled" in item for item in result.errors)
    assert any("database_url_required" in item for item in result.errors)
    assert any("redis_url_required" in item for item in result.errors)
    assert any("mcp_server_command_allowlist" in item for item in result.errors)
    assert any("mcp_tool_allowlist" in item for item in result.errors)
    assert any("real_llm_model" in item for item in result.errors)
    assert any("real_llm_api_key_present" in item for item in result.errors)
    assert any("cors_allow_origins" in item for item in result.errors)
    assert any("security_headers_enabled" in item for item in result.errors)
    assert any("request_size_limit_enabled" in item for item in result.errors)
    assert any("request_size_limit_bytes" in item for item in result.errors)
    assert any("rate_limit_enabled" in item for item in result.errors)
    assert any("rate_limit_backend_valid" in item for item in result.errors)
    assert any("rate_limit_requests_per_minute" in item for item in result.errors)
    assert any("rate_limit_burst" in item for item in result.errors)
    assert any("structured_logging_enabled" in item for item in result.errors)
    assert any("log_redaction_enabled" in item for item in result.errors)
    assert any("log_level_production" in item for item in result.errors)
    assert any("audit_retention_enabled" in item for item in result.errors)
    assert any("audit_retention_days" in item for item in result.errors)
    assert any("audit_export_max_rows" in item for item in result.errors)
    assert any("audit_export_redaction_enabled" in item for item in result.errors)


def test_production_mode_pass_without_secret_leak(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:safe-password-001@db:5432/project_b")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")

    result = run_deployment_checks()
    payload = result.model_dump_json()
    assert result.ok is True
    assert "very-strong-secret-32-bytes-production" not in payload
    assert "password@db" not in payload


def test_production_rejects_placeholder_jwt_secret(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret", "change-me-strong-secret")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("jwt_secret" in item for item in result.errors)


def test_production_rejects_database_placeholder_password(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:change-me@db:5432/project_b")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("database_url_secret_strength" in item for item in result.errors)
    assert "change-me@db" not in result.model_dump_json()


def test_production_valid_postgres_and_redis_passes(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:strong-safe-password@postgres:5432/project_b")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")

    result = run_deployment_checks()
    assert result.ok is True


def test_deployment_check_json_does_not_contain_password_fragments(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:sensitive-pass@db:5432/project_b")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://:redis-sensitive-pass@redis:6379/0")

    payload = run_deployment_checks().model_dump_json()
    assert "sensitive-pass" not in payload
    assert "redis-sensitive-pass" not in payload
    assert "very-strong-secret-32-bytes-production" not in payload


def test_deployment_check_api_always_200(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-change-me-please-32-bytes")
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://agent:change-me@db:5432/project_b")

    response = client.get("/deployment/check")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert isinstance(data["errors"], list)
    assert "dev-only-change-me-please-32-bytes" not in str(data)
    assert "change-me@db" not in str(data)


def test_deployment_check_api_accessible_when_auth_rbac_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
    response = client.get("/deployment/check")
    assert response.status_code == 200


def test_production_rejects_wildcard_cors(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "cors_allow_origins", "*")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("cors_allow_origins" in item for item in result.errors)


def test_production_rejects_security_headers_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "security_headers_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("security_headers_enabled" in item for item in result.errors)


def test_production_rejects_request_size_limit_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "request_size_limit_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("request_size_limit_enabled" in item for item in result.errors)


def test_production_rejects_rate_limit_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("rate_limit_enabled" in item for item in result.errors)


def test_production_redis_rate_limit_backend_requires_redis(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "redis_enabled", False)
    monkeypatch.setattr(settings, "redis_url", "")

    result = run_deployment_checks()

    assert result.ok is False
    assert any("rate_limit_redis_enabled" in item for item in result.errors)
    assert any("rate_limit_redis_url" in item for item in result.errors)


def test_production_redis_rate_limit_backend_passes_with_redis_config(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")

    result = run_deployment_checks()

    assert result.ok is True


def test_production_rejects_structured_logging_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "structured_logging_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("structured_logging_enabled" in item for item in result.errors)


def test_production_rejects_log_redaction_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "log_redaction_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("log_redaction_enabled" in item for item in result.errors)


def test_production_rejects_debug_log_level(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "log_level", "DEBUG")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("log_level_production" in item for item in result.errors)


def test_production_rejects_audit_retention_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "audit_retention_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("audit_retention_enabled" in item for item in result.errors)


def test_production_rejects_audit_export_max_rows_out_of_range(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "audit_export_max_rows", 10001)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("audit_export_max_rows" in item for item in result.errors)


def test_production_rejects_audit_export_redaction_disabled(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("audit_export_redaction_enabled" in item for item in result.errors)


def test_production_oidc_disabled_warning_only(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", False)

    result = run_deployment_checks()
    assert result.ok is True
    assert any("oidc_enabled" in item for item in result.warnings)


def test_production_oidc_enabled_requires_required_settings(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "")
    monkeypatch.setattr(settings, "oidc_client_id", "")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "MISSING_OIDC_SECRET")
    monkeypatch.delenv("MISSING_OIDC_SECRET", raising=False)

    result = run_deployment_checks()
    assert result.ok is False
    assert any("oidc_issuer_url" in item for item in result.errors)
    assert any("oidc_client_id" in item for item in result.errors)
    assert any("oidc_redirect_uri" in item for item in result.errors)
    assert any("oidc_client_secret_present" in item for item in result.errors)


def test_production_oidc_enabled_rejects_http_urls(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "http://idp.example.com/realms/demo")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b-console")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "http://console.example.com/callback")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_TEST")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_TEST", "oidc-secret-value")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("oidc_issuer_url_https" in item for item in result.errors)
    assert any("oidc_redirect_uri_https" in item for item in result.errors)
    assert "oidc-secret-value" not in result.model_dump_json()


def test_production_oidc_enabled_valid_https_passes(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://idp.example.com/realms/demo")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b-console")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://console.example.com/auth/callback")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET_TEST_OK")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_TEST_OK", "oidc-secret-value")

    result = run_deployment_checks()
    assert result.ok is True
    assert "oidc-secret-value" not in result.model_dump_json()


def test_production_rejects_invalid_oidc_roles(monkeypatch):
    _set_production_secure_defaults(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://idp.example.com/realms/demo")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b-console")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://console.example.com/auth/callback")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_ROLE_TEST_SECRET")
    monkeypatch.setenv("OIDC_ROLE_TEST_SECRET", "oidc-secret-value")
    monkeypatch.setattr(settings, "oidc_allowed_roles", "admin,viewer,guest")
    monkeypatch.setattr(settings, "oidc_default_role", "guest")

    result = run_deployment_checks()
    assert result.ok is False
    assert any("oidc_allowed_roles_valid" in item for item in result.errors)
    assert any("oidc_default_role_valid" in item for item in result.errors)
