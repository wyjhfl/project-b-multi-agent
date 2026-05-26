from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.core.config import Settings, settings
from app.core.security_headers import parse_csv_config

_DISALLOWED_JWT_SECRETS = {
    "",
    "dev-only-change-me-please-32-bytes",
    "change-me-strong-secret",
    "change-me",
    "replace-me",
}
_PLACEHOLDER_TOKENS = {
    "change-me",
    "changeme",
    "replace-me",
    "replace_me",
    "example",
}
_WEAK_PASSWORD_VALUES = {
    "password",
    "password123",
    "secret",
    "token",
    "123456",
    "admin",
}


class DeploymentCheckResult(BaseModel):
    ok: bool = True
    environment: str = "development"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)


def _add_check(
    result: DeploymentCheckResult,
    *,
    name: str,
    passed: bool,
    level: str,
    detail: str,
) -> None:
    result.checks.append(
        {
            "name": name,
            "passed": passed,
            "level": level,
            "detail": detail,
        }
    )
    if passed:
        return
    if level == "error":
        result.errors.append(f"{name}: {detail}")
        result.ok = False
    else:
        result.warnings.append(f"{name}: {detail}")


def _contains_placeholder_token(value: str) -> bool:
    lowered = (value or "").lower()
    return any(token in lowered for token in _PLACEHOLDER_TOKENS)


def _extract_url_password(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
    except Exception:
        return ""
    return parsed.password or ""


def _is_weak_jwt_secret(secret: str) -> bool:
    normalized = (secret or "").strip()
    if normalized in _DISALLOWED_JWT_SECRETS:
        return True
    return len(normalized) < 32


def _is_obvious_placeholder_password(password: str) -> bool:
    normalized = (password or "").strip().lower()
    if not normalized:
        return False
    if normalized in _WEAK_PASSWORD_VALUES:
        return True
    return _contains_placeholder_token(normalized)


def _is_cors_origin_policy_valid(current: Settings) -> tuple[bool, str]:
    origins = parse_csv_config(current.cors_allow_origins)
    if not origins:
        return False, "CORS 启用时 CORS_ALLOW_ORIGINS 不能为空。"
    if "*" in origins:
        return False, "production 环境不允许 CORS_ALLOW_ORIGINS 使用通配符 *。"
    return True, ""


def run_deployment_checks(runtime_settings: Settings | None = None) -> DeploymentCheckResult:
    current = runtime_settings or settings
    env = (current.app_env or "development").strip().lower()
    result = DeploymentCheckResult(ok=True, environment=env)

    is_production = env == "production"
    if not is_production:
        _add_check(
            result,
            name="app_env",
            passed=False,
            level="warning",
            detail="当前非 production 环境，跳过生产阻断门禁（默认开发路径保持不变）。",
        )
        return result

    jwt_secret = (current.jwt_secret or "").strip()
    _add_check(
        result,
        name="jwt_secret",
        passed=not _is_weak_jwt_secret(jwt_secret),
        level="error",
        detail="JWT_SECRET 不能为空、不能使用占位值，且长度必须不少于 32 字符。",
    )

    _add_check(
        result,
        name="auth_enabled",
        passed=bool(current.auth_enabled),
        level="error",
        detail="production 环境要求 AUTH_ENABLED=true。",
    )
    _add_check(
        result,
        name="rbac_enabled",
        passed=bool(current.rbac_enabled),
        level="error",
        detail="production 环境要求 RBAC_ENABLED=true。",
    )

    if bool(current.cors_enabled):
        cors_ok, cors_error = _is_cors_origin_policy_valid(current)
        _add_check(
            result,
            name="cors_allow_origins",
            passed=cors_ok,
            level="error",
            detail=cors_error or "CORS origin 配置合法。",
        )

    _add_check(
        result,
        name="security_headers_enabled",
        passed=bool(current.security_headers_enabled),
        level="error",
        detail="production 环境要求 SECURITY_HEADERS_ENABLED=true。",
    )

    if (current.storage_backend or "").strip().lower() == "postgres":
        database_url = (current.database_url or "").strip()
        _add_check(
            result,
            name="database_url_required",
            passed=bool(database_url),
            level="error",
            detail="STORAGE_BACKEND=postgres 时 DATABASE_URL 必须非空。",
        )
        if database_url:
            has_disallowed_token = "replace-me" in database_url.lower() or ":change-me@" in database_url.lower()
            password = _extract_url_password(database_url)
            has_placeholder_password = _is_obvious_placeholder_password(password)
            _add_check(
                result,
                name="database_url_secret_strength",
                passed=not has_disallowed_token and not has_placeholder_password,
                level="error",
                detail="DATABASE_URL 不可使用占位密码或弱口令占位标识。",
            )

    if bool(current.redis_enabled):
        redis_url = (current.redis_url or "").strip()
        _add_check(
            result,
            name="redis_url_required",
            passed=bool(redis_url),
            level="error",
            detail="REDIS_ENABLED=true 时 REDIS_URL 必须非空。",
        )
        if redis_url:
            _add_check(
                result,
                name="redis_url_secret_strength",
                passed=not _contains_placeholder_token(redis_url),
                level="error",
                detail="REDIS_URL 不可包含占位密钥标识。",
            )

    if (current.mcp_mode or "").strip().lower() == "real":
        _add_check(
            result,
            name="mcp_server_command_allowlist",
            passed=bool((current.mcp_server_command_allowlist or "").strip()),
            level="error",
            detail="MCP_MODE=real 时 MCP_SERVER_COMMAND_ALLOWLIST 必须非空。",
        )

    if bool(current.real_llm_acceptance_enabled):
        _add_check(
            result,
            name="real_llm_model",
            passed=bool((current.real_llm_model or "").strip()),
            level="error",
            detail="REAL_LLM_ACCEPTANCE_ENABLED=true 时 REAL_LLM_MODEL 必须非空。",
        )
        env_name = (current.real_llm_api_key_env or "").strip()
        _add_check(
            result,
            name="real_llm_api_key_env",
            passed=bool(env_name),
            level="error",
            detail="REAL_LLM_ACCEPTANCE_ENABLED=true 时 REAL_LLM_API_KEY_ENV 必须配置。",
        )
        has_key = bool(env_name) and bool(os.getenv(env_name, "").strip())
        _add_check(
            result,
            name="real_llm_api_key_present",
            passed=has_key,
            level="error",
            detail="REAL_LLM_API_KEY_ENV 指向的环境变量必须存在且非空。",
        )

    return result
