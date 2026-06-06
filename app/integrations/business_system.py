from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from app.harness.gateway.tool_gateway import ToolGateway
from app.models.schemas import RiskLevel, ToolSpec

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(token|api[_-]?key|client[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)https?://[^/\s:]+:[^@\s]+@[^,\s]+"),
]


@dataclass(frozen=True)
class BusinessSystemConfig:
    enabled: bool
    read_only: bool
    write_enabled: bool
    approval_required: bool
    audit_required: bool
    system_name: str
    base_url_env: str
    token_env: str
    tool_allowlist: tuple[str, ...]
    write_tool_allowlist: tuple[str, ...]
    timeout_seconds: float
    read_probe_path: str
    auth_header_name: str
    auth_scheme: str

    @property
    def base_url_present(self) -> bool:
        return bool(self.base_url_env and os.getenv(self.base_url_env, "").strip())

    @property
    def token_present(self) -> bool:
        return bool(self.token_env and os.getenv(self.token_env, "").strip())


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(raw: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(raw or "").split(",") if item.strip())


def load_business_system_config() -> BusinessSystemConfig:
    timeout_raw = os.getenv("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = max(0.1, min(float(timeout_raw), 60.0))
    except ValueError:
        timeout_seconds = 10.0
    auth_scheme_raw = os.getenv("BUSINESS_SYSTEM_AUTH_SCHEME")
    return BusinessSystemConfig(
        enabled=_env_enabled("BUSINESS_INTEGRATION_ENABLED"),
        read_only=_env_enabled("BUSINESS_INTEGRATION_READ_ONLY"),
        write_enabled=_env_enabled("BUSINESS_INTEGRATION_WRITE_ENABLED"),
        approval_required=_env_enabled("BUSINESS_INTEGRATION_APPROVAL_REQUIRED"),
        audit_required=_env_enabled("BUSINESS_INTEGRATION_AUDIT_REQUIRED"),
        system_name=(os.getenv("BUSINESS_SYSTEM_NAME", "") or "business_system").strip() or "business_system",
        base_url_env=(os.getenv("BUSINESS_SYSTEM_BASE_URL_ENV", "") or "").strip(),
        token_env=(os.getenv("BUSINESS_SYSTEM_TOKEN_ENV", "") or "").strip(),
        tool_allowlist=_parse_csv(os.getenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST")),
        write_tool_allowlist=_parse_csv(os.getenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST")),
        timeout_seconds=timeout_seconds,
        read_probe_path=(os.getenv("BUSINESS_SYSTEM_READ_PROBE_PATH", "") or "/health").strip() or "/health",
        auth_header_name=(os.getenv("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "") or "Authorization").strip()
        or "Authorization",
        auth_scheme=("Bearer" if auth_scheme_raw is None else auth_scheme_raw.strip()),
    )


def redact_secret_like(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): redact_secret_like(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret_like(item) for item in value]
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def safe_config_summary(config: BusinessSystemConfig) -> dict[str, Any]:
    return {
        "enabled": config.enabled,
        "read_only": config.read_only,
        "write_enabled": config.write_enabled,
        "approval_required": config.approval_required,
        "audit_required": config.audit_required,
        "system_name": config.system_name,
        "base_url_env": config.base_url_env,
        "base_url_present": config.base_url_present,
        "token_env": config.token_env,
        "token_present": config.token_present,
        "tool_allowlist_count": len(config.tool_allowlist),
        "write_tool_allowlist_count": len(config.write_tool_allowlist),
        "timeout_seconds": config.timeout_seconds,
        "read_probe_path_configured": bool(config.read_probe_path),
        "auth_header_name": config.auth_header_name,
        "auth_scheme_configured": bool(config.auth_scheme),
    }


def _base_url_from_env(config: BusinessSystemConfig) -> str:
    return os.getenv(config.base_url_env, "").strip() if config.base_url_env else ""


def _token_from_env(config: BusinessSystemConfig) -> str:
    return os.getenv(config.token_env, "").strip() if config.token_env else ""


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except Exception:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def _is_safe_header_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9-]+", value or ""))


def _contains_control_chars(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _is_safe_auth_scheme(value: str) -> bool:
    return not value or bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9._~-]*", value))


def _is_safe_probe_path(value: str) -> bool:
    return value.startswith("/") and not value.startswith("//") and not _contains_control_chars(value)


def _auth_header(config: BusinessSystemConfig) -> dict[str, str]:
    token = _token_from_env(config)
    header_name = config.auth_header_name or "Authorization"
    if config.auth_scheme:
        return {header_name: f"{config.auth_scheme} {token}"}
    return {header_name: token}


def build_business_read_probe_tool(config: BusinessSystemConfig):
    def business_read_probe(path: str | None = None) -> dict[str, Any]:
        if not config.enabled:
            return {"error": "business_integration_disabled"}
        if not config.read_only:
            return {"error": "business_integration_read_only_not_enabled"}
        if not config.base_url_present:
            return {"error": "business_system_base_url_missing"}
        if not config.token_present:
            return {"error": "business_system_token_missing"}

        base_url = _base_url_from_env(config)
        if not _is_http_url(base_url):
            return {"error": "business_system_base_url_invalid"}
        if not _is_safe_header_name(config.auth_header_name):
            return {"error": "business_system_auth_header_name_invalid"}
        if not _is_safe_auth_scheme(config.auth_scheme):
            return {"error": "business_system_auth_scheme_invalid"}
        if _contains_control_chars(_token_from_env(config)):
            return {"error": "business_system_token_invalid"}

        probe_path = path or config.read_probe_path
        if not _is_safe_probe_path(str(probe_path)):
            return {"error": "business_probe_path_must_be_absolute"}

        url = urljoin(base_url.rstrip("/") + "/", str(probe_path).lstrip("/"))
        headers = {
            "Accept": "application/json",
            **_auth_header(config),
        }
        started = time.monotonic()
        try:
            request = Request(url, headers=headers, method="GET")
            with urlopen(request, timeout=config.timeout_seconds) as response:
                body = response.read(4096)
                status_code = int(getattr(response, "status", 0) or 0)
                content_type = response.headers.get("content-type", "")
        except Exception as exc:
            return {
                "error": "business_read_probe_failed",
                "error_type": exc.__class__.__name__,
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
            }

        parsed_body: Any = None
        if body:
            try:
                parsed_body = json.loads(body.decode("utf-8"))
            except Exception:
                parsed_body = {"body_preview": body[:128].decode("utf-8", errors="replace")}

        return {
            **(
                {"error": "business_read_probe_non_2xx", "status_code": status_code}
                if status_code < 200 or status_code >= 300
                else {}
            ),
            "status_code": status_code,
            "content_type": content_type,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "body": redact_secret_like(parsed_body),
        }

    return business_read_probe


def register_business_system_tools(gateway: ToolGateway, config: BusinessSystemConfig | None = None) -> list[ToolSpec]:
    effective = config or load_business_system_config()
    specs: list[ToolSpec] = []
    if "business_read_probe" in effective.tool_allowlist:
        spec = ToolSpec(
            tool_name="business_read_probe",
            description="业务系统只读连通性探测",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            output_schema={"type": "object"},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=effective.timeout_seconds,
            source="local",
            is_local=True,
        )
        gateway.register(spec, build_business_read_probe_tool(effective))
        specs.append(spec)
    return specs
