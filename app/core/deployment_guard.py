from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, settings

_DEV_JWT_SECRET = "dev-only-change-me-please-32-bytes"


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
    jwt_ok = bool(jwt_secret) and jwt_secret != _DEV_JWT_SECRET
    _add_check(
        result,
        name="jwt_secret",
        passed=jwt_ok,
        level="error",
        detail="JWT_SECRET 不能为空且不能使用默认开发占位值。",
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

    if (current.storage_backend or "").strip().lower() == "postgres":
        _add_check(
            result,
            name="database_url",
            passed=bool((current.database_url or "").strip()),
            level="error",
            detail="STORAGE_BACKEND=postgres 时 DATABASE_URL 必须非空。",
        )

    if bool(current.redis_enabled):
        _add_check(
            result,
            name="redis_url",
            passed=bool((current.redis_url or "").strip()),
            level="error",
            detail="REDIS_ENABLED=true 时 REDIS_URL 必须非空。",
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
