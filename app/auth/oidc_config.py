from __future__ import annotations

import os
from typing import Any

from app.core.config import Settings

_ALLOWED_ROLES = {"admin", "operator", "viewer", "auditor"}


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _normalize_roles(raw: str) -> list[str]:
    normalized: list[str] = []
    for role in _parse_csv(raw):
        lowered = role.lower()
        if lowered not in normalized:
            normalized.append(lowered)
    return normalized


def _is_https_url(url: str) -> bool:
    text = (url or "").strip().lower()
    return text.startswith("https://") and len(text) > len("https://")


def _is_localhost_url(url: str) -> bool:
    text = (url or "").strip().lower()
    return text.startswith("http://localhost") or text.startswith("http://127.0.0.1")


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
        errors.append("OIDC_ALLOWED_ROLES 不能为空")
    if unknown_roles:
        errors.append("OIDC_ALLOWED_ROLES 仅允许 admin/operator/viewer/auditor")

    default_role = (current_settings.oidc_default_role or "").strip().lower()
    if not default_role:
        errors.append("OIDC_DEFAULT_ROLE 不能为空")
    elif default_role not in _ALLOWED_ROLES:
        errors.append("OIDC_DEFAULT_ROLE 仅允许 admin/operator/viewer/auditor")
    elif default_role not in allowed_roles:
        errors.append("OIDC_DEFAULT_ROLE 必须包含在 OIDC_ALLOWED_ROLES 中")

    if not bool(current_settings.oidc_enabled):
        return {"errors": errors, "warnings": warnings}

    issuer_url = (current_settings.oidc_issuer_url or "").strip()
    client_id = (current_settings.oidc_client_id or "").strip()
    redirect_uri = (current_settings.oidc_redirect_uri or "").strip()
    client_secret_env = (current_settings.oidc_client_secret_env or "").strip()
    role_claim = (current_settings.oidc_role_claim or "").strip()

    if not issuer_url:
        errors.append("OIDC_ISSUER_URL 不能为空")
    if not client_id:
        errors.append("OIDC_CLIENT_ID 不能为空")
    if not redirect_uri:
        errors.append("OIDC_REDIRECT_URI 不能为空")
    if not client_secret_env:
        errors.append("OIDC_CLIENT_SECRET_ENV 不能为空")
    if not role_claim:
        warnings.append("OIDC_ROLE_CLAIM 为空，将使用默认 roles")

    if client_secret_env and not get_oidc_client_secret(current_settings):
        errors.append(f"{client_secret_env} 未注入或为空")

    if bool(current_settings.oidc_require_https):
        env_name = (current_settings.app_env or "development").strip().lower()
        if issuer_url and not _is_https_url(issuer_url):
            if env_name == "development" and _is_localhost_url(issuer_url):
                warnings.append("development 环境允许 localhost issuer 使用 http")
            else:
                errors.append("OIDC_ISSUER_URL 必须使用 https")
        if redirect_uri and not _is_https_url(redirect_uri):
            if env_name == "development" and _is_localhost_url(redirect_uri):
                warnings.append("development 环境允许 localhost redirect_uri 使用 http")
            else:
                errors.append("OIDC_REDIRECT_URI 必须使用 https")

    return {"errors": errors, "warnings": warnings}


def map_oidc_roles(claims: dict[str, Any], current_settings: Settings) -> list[str]:
    allowed_roles = [role for role in _normalize_roles(current_settings.oidc_allowed_roles) if role in _ALLOWED_ROLES]
    default_role = (current_settings.oidc_default_role or "viewer").strip().lower() or "viewer"

    if default_role not in allowed_roles and allowed_roles:
        default_role = allowed_roles[0]

    claim_name = (current_settings.oidc_role_claim or "roles").strip()
    raw_roles = claims.get(claim_name, [])

    if isinstance(raw_roles, str):
        source_roles = [raw_roles]
    elif isinstance(raw_roles, list):
        source_roles = [str(item) for item in raw_roles]
    else:
        source_roles = []

    mapped: list[str] = []
    for role in source_roles:
        lowered = role.strip().lower()
        if lowered in allowed_roles and lowered not in mapped:
            mapped.append(lowered)

    if mapped:
        return mapped
    return [default_role]


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
