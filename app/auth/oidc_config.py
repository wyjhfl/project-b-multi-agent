from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from app.core.config import Settings

_ALLOWED_ROLES = {"admin", "operator", "viewer", "auditor"}


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _normalize_roles(value: str) -> list[str]:
    normalized: list[str] = []
    for role in _parse_csv(value):
        lowered = role.lower()
        if lowered not in normalized:
            normalized.append(lowered)
    return normalized


def _is_localhost_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.lower() in {"localhost", "127.0.0.1", "::1"}


def _is_https_url(url: str) -> bool:
    try:
        parsed = urlsplit((url or "").strip())
    except Exception:
        return False
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _is_http_localhost_url(url: str) -> bool:
    try:
        parsed = urlsplit((url or "").strip())
    except Exception:
        return False
    return parsed.scheme.lower() == "http" and _is_localhost_host(parsed.hostname)


def get_oidc_client_secret(current_settings: Settings) -> str:
    env_name = (current_settings.oidc_client_secret_env or "").strip()
    if not env_name:
        return ""
    return os.getenv(env_name, "").strip()


def validate_oidc_settings(current_settings: Settings) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    allowed_roles = _normalize_roles(current_settings.oidc_allowed_roles)
    unknown_roles = [role for role in allowed_roles if role not in _ALLOWED_ROLES]
    if not allowed_roles:
        errors.append("OIDC_ALLOWED_ROLES 不能为空。")
    if unknown_roles:
        errors.append("OIDC_ALLOWED_ROLES 只能包含 admin/operator/viewer/auditor。")

    default_role = (current_settings.oidc_default_role or "").strip().lower()
    if default_role not in _ALLOWED_ROLES:
        errors.append("OIDC_DEFAULT_ROLE 必须是 admin/operator/viewer/auditor 之一。")
    elif default_role not in allowed_roles:
        errors.append("OIDC_DEFAULT_ROLE 必须出现在 OIDC_ALLOWED_ROLES 中。")

    if not bool(current_settings.oidc_enabled):
        return {"errors": errors, "warnings": warnings}

    issuer_url = (current_settings.oidc_issuer_url or "").strip()
    client_id = (current_settings.oidc_client_id or "").strip()
    redirect_uri = (current_settings.oidc_redirect_uri or "").strip()
    client_secret_env = (current_settings.oidc_client_secret_env or "").strip()
    role_claim = (current_settings.oidc_role_claim or "").strip()

    if not issuer_url:
        errors.append("OIDC_ISSUER_URL 不能为空。")
    if not client_id:
        errors.append("OIDC_CLIENT_ID 不能为空。")
    if not redirect_uri:
        errors.append("OIDC_REDIRECT_URI 不能为空。")
    if not client_secret_env:
        errors.append("OIDC_CLIENT_SECRET_ENV 不能为空。")
    if not role_claim:
        warnings.append("OIDC_ROLE_CLAIM 为空时将使用默认角色映射。")

    if client_secret_env and not get_oidc_client_secret(current_settings):
        errors.append(f"环境变量 {client_secret_env} 未设置或为空。")

    env = (current_settings.app_env or "development").strip().lower()
    if bool(current_settings.oidc_require_https):
        for field_name, url in (("OIDC_ISSUER_URL", issuer_url), ("OIDC_REDIRECT_URI", redirect_uri)):
            if not url:
                continue
            if _is_https_url(url):
                continue
            if env == "development" and _is_http_localhost_url(url):
                warnings.append(f"development 环境允许 {field_name} 使用 localhost 的 http 地址。")
            else:
                errors.append(f"{field_name} 必须使用 https 地址。")

    return {"errors": errors, "warnings": warnings}


def map_oidc_roles(claims: dict[str, Any], current_settings: Settings) -> list[str]:
    allowed_roles = [role for role in _normalize_roles(current_settings.oidc_allowed_roles) if role in _ALLOWED_ROLES]
    default_role = (current_settings.oidc_default_role or "viewer").strip().lower()
    if default_role not in allowed_roles:
        default_role = "viewer"
    if default_role not in allowed_roles:
        allowed_roles.append(default_role)

    claim_name = (current_settings.oidc_role_claim or "roles").strip()
    raw_roles = claims.get(claim_name)

    candidates: list[str] = []
    if isinstance(raw_roles, str):
        candidates = [item.strip().lower() for item in raw_roles.split(",") if item.strip()]
    elif isinstance(raw_roles, (list, tuple, set)):
        candidates = [str(item).strip().lower() for item in raw_roles if str(item).strip()]

    mapped: list[str] = []
    for role in candidates:
        if role in allowed_roles and role not in mapped:
            mapped.append(role)

    if not mapped:
        return [default_role]
    return mapped


def build_oidc_status(current_settings: Settings) -> dict[str, Any]:
    validation = validate_oidc_settings(current_settings)
    client_secret_env = (current_settings.oidc_client_secret_env or "").strip()

    return {
        "enabled": bool(current_settings.oidc_enabled),
        "issuer_configured": bool((current_settings.oidc_issuer_url or "").strip()),
        "client_id_configured": bool((current_settings.oidc_client_id or "").strip()),
        "redirect_uri_configured": bool((current_settings.oidc_redirect_uri or "").strip()),
        "client_secret_env": client_secret_env,
        "client_secret_present": bool(client_secret_env and get_oidc_client_secret(current_settings)),
        "scopes": _parse_csv(current_settings.oidc_scopes),
        "role_claim": (current_settings.oidc_role_claim or "roles").strip() or "roles",
        "default_role": (current_settings.oidc_default_role or "viewer").strip().lower() or "viewer",
        "allowed_roles": _normalize_roles(current_settings.oidc_allowed_roles),
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }
