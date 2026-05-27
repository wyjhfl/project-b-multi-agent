from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.agent.nl2sql.provider import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderModelError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    UnknownProviderError,
    create_provider,
)
from app.core.config import Settings, settings as global_settings


@dataclass
class LLMPreflightResult:
    allowed: bool
    status: str
    provider: str
    model: str
    base_url: str
    api_key_env: str
    api_key_present: bool
    network_check_allowed: bool
    network_check_requested: bool
    network_check_executed: bool
    checks: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key_present": self.api_key_present,
            "network_check_allowed": self.network_check_allowed,
            "network_check_requested": self.network_check_requested,
            "network_check_executed": self.network_check_executed,
            # 兼容历史字段
            "network_check_enabled": self.network_check_executed,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "latency_ms": self.latency_ms,
        }


def _append_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})


def _mask_env_name(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 3:
        return "***"
    return text[:3] + "***"


def _redact_base_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "@" not in text:
        return text
    if "://" in lowered:
        scheme, rest = text.split("://", 1)
        if "@" in rest:
            _, host_part = rest.rsplit("@", 1)
            return f"{scheme}://***@{host_part}"
    return "***"


def _validate_timeout_and_retry(cfg: Settings, checks: list[dict[str, Any]], warnings: list[str], errors: list[str]) -> None:
    timeout_ok = 1.0 <= float(cfg.real_llm_preflight_timeout_seconds) <= 120.0
    _append_check(
        checks,
        "preflight_timeout_range",
        timeout_ok,
        f"real_llm_preflight_timeout_seconds={cfg.real_llm_preflight_timeout_seconds}",
    )
    if not timeout_ok:
        errors.append("real_llm_preflight_timeout_seconds 超出范围（1~120）")

    llm_timeout_ok = 1.0 <= float(cfg.llm_timeout_seconds) <= 300.0
    _append_check(checks, "llm_timeout_range", llm_timeout_ok, f"llm_timeout_seconds={cfg.llm_timeout_seconds}")
    if not llm_timeout_ok:
        warnings.append("llm_timeout_seconds 超出建议范围（1~300）")

    llm_retry_ok = 0 <= int(cfg.llm_max_retries) <= 5
    _append_check(checks, "llm_retry_range", llm_retry_ok, f"llm_max_retries={cfg.llm_max_retries}")
    if not llm_retry_ok:
        warnings.append("llm_max_retries 超出建议范围（0~5）")

    llm_backoff_ok = 0.0 <= float(cfg.llm_retry_backoff_seconds) <= 10.0
    _append_check(
        checks,
        "llm_backoff_range",
        llm_backoff_ok,
        f"llm_retry_backoff_seconds={cfg.llm_retry_backoff_seconds}",
    )
    if not llm_backoff_ok:
        warnings.append("llm_retry_backoff_seconds 超出建议范围（0~10）")


def _perform_network_check(
    cfg: Settings,
    provider_name: str,
    model_name: str,
    api_key: str,
    base_url: str,
) -> tuple[bool, str, float]:
    provider = create_provider(
        provider_name=provider_name,
        api_key=api_key,
        model=model_name,
        base_url=base_url,
        timeout_seconds=cfg.real_llm_preflight_timeout_seconds,
        max_retries=min(max(int(cfg.llm_max_retries), 0), 1),
        retry_backoff_seconds=max(float(cfg.llm_retry_backoff_seconds), 0.0),
        temperature=0.0,
    )
    metadata = provider.generate_with_metadata("请只返回: ok")
    latency_ms = float(getattr(metadata, "latency_ms", 0.0) or 0.0)
    if not (metadata.content or "").strip():
        return False, "network_check_empty_content", latency_ms
    return True, "network_check_ok", latency_ms


def run_llm_provider_preflight(
    settings: Settings | None = None,
    perform_network_check: bool = False,
) -> LLMPreflightResult:
    cfg = settings or global_settings
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    provider_name = (cfg.real_llm_provider or "").strip().lower()
    model_name = (cfg.real_llm_model or "").strip()
    base_url_text = (cfg.real_llm_base_url or "").strip()
    api_key_env_name = (cfg.real_llm_api_key_env or "").strip()

    acceptance_enabled = bool(cfg.real_llm_acceptance_enabled)
    preflight_enabled = bool(cfg.real_llm_preflight_enabled)
    _append_check(checks, "acceptance_enabled", acceptance_enabled, f"real_llm_acceptance_enabled={acceptance_enabled}")
    _append_check(checks, "preflight_enabled", preflight_enabled, f"real_llm_preflight_enabled={preflight_enabled}")
    if not acceptance_enabled:
        warnings.append("real_llm_acceptance_enabled=false")
    if not preflight_enabled:
        warnings.append("real_llm_preflight_enabled=false")

    if not acceptance_enabled or not preflight_enabled:
        if perform_network_check:
            warnings.append("network_check_skipped_disabled")
        _append_check(
            checks,
            "disabled_mode",
            True,
            "preflight disabled: 跳过 provider/model/api_key 强校验与网络检查",
        )
        _append_check(
            checks,
            "provider_observed",
            bool(provider_name),
            f"provider={provider_name or '<empty>'}",
        )
        _append_check(
            checks,
            "model_observed",
            bool(model_name),
            f"model={'<set>' if bool(model_name) else '<empty>'}",
        )
        _append_check(
            checks,
            "api_key_env_observed",
            bool(api_key_env_name),
            f"real_llm_api_key_env={_mask_env_name(api_key_env_name)}",
        )
        has_api_key_disabled = bool(os.getenv(api_key_env_name)) if api_key_env_name else False
        _append_check(
            checks,
            "api_key_present_observed",
            has_api_key_disabled,
            "api key in env: present" if has_api_key_disabled else "api key in env: missing",
        )
        _append_check(
            checks,
            "network_check_gate",
            bool(cfg.real_llm_preflight_network_check),
            f"real_llm_preflight_network_check={bool(cfg.real_llm_preflight_network_check)}",
        )
        _validate_timeout_and_retry(cfg, checks, warnings, errors)
        return LLMPreflightResult(
            allowed=False,
            status="disabled",
            provider=provider_name,
            model=model_name,
            base_url=_redact_base_url(base_url_text),
            api_key_env=api_key_env_name,
            api_key_present=has_api_key_disabled,
            network_check_allowed=bool(cfg.real_llm_preflight_network_check),
            network_check_requested=perform_network_check,
            network_check_executed=False,
            checks=checks,
            warnings=warnings,
            errors=[],
            latency_ms=0.0,
        )

    provider_ok = provider_name in {"litellm"}
    _append_check(checks, "provider_supported", provider_ok, f"provider={provider_name or '<empty>'}")
    if not provider_ok:
        errors.append(f"unsupported provider: {provider_name or '<empty>'}")

    _append_check(
        checks,
        "base_url_configured",
        bool(base_url_text),
        "base_url: configured" if base_url_text else "base_url: empty (provider 默认地址)",
    )

    model_ok = bool(model_name)
    _append_check(checks, "model_configured", model_ok, f"model={'<set>' if model_ok else '<empty>'}")
    if not model_ok:
        errors.append("real_llm_model is empty")

    env_name_ok = bool(api_key_env_name)
    _append_check(
        checks,
        "api_key_env_name_configured",
        env_name_ok,
        f"real_llm_api_key_env={_mask_env_name(api_key_env_name)}",
    )
    if not env_name_ok:
        errors.append("real_llm_api_key_env is empty")

    api_key_value = os.getenv(api_key_env_name) if env_name_ok else None
    has_api_key = bool(api_key_value)
    _append_check(checks, "api_key_present", has_api_key, "api key in env: present" if has_api_key else "api key in env: missing")
    if env_name_ok and not has_api_key:
        errors.append(f"missing api key env: {api_key_env_name}")

    _validate_timeout_and_retry(cfg, checks, warnings, errors)

    network_allowed = bool(cfg.real_llm_preflight_network_check)
    _append_check(
        checks,
        "network_check_gate",
        network_allowed,
        f"real_llm_preflight_network_check={network_allowed}",
    )

    ready_for_network = (
        acceptance_enabled
        and preflight_enabled
        and provider_ok
        and model_ok
        and has_api_key
        and not errors
    )

    network_check_executed = False
    network_latency_ms = 0.0
    if perform_network_check and not network_allowed:
        errors.append("network_check_not_allowed")
    if perform_network_check and network_allowed and not ready_for_network:
        errors.append("network_check_requires_ready_configuration")

    if perform_network_check and network_allowed and ready_for_network:
        try:
            ok, detail, network_latency_ms = _perform_network_check(
                cfg,
                provider_name,
                model_name,
                api_key_value or "",
                base_url_text,
            )
            network_check_executed = True
            _append_check(checks, "network_check", ok, detail)
            _append_check(checks, "network_check_latency_ms", True, f"{network_latency_ms:.2f}")
            if not ok:
                errors.append(detail)
        except (
            ProviderConfigError,
            ProviderAuthError,
            ProviderTimeoutError,
            ProviderRateLimitError,
            ProviderModelError,
            ProviderResponseError,
            UnknownProviderError,
            Exception,
        ) as exc:
            network_check_executed = True
            _append_check(checks, "network_check", False, "network_check_exception")
            errors.append(f"network_check_failed:{exc.__class__.__name__}")

    if errors:
        status = "failed"
    elif not acceptance_enabled or not preflight_enabled:
        status = "disabled"
    elif network_check_executed:
        status = "passed"
    else:
        status = "ready"

    return LLMPreflightResult(
        allowed=ready_for_network and not errors,
        status=status,
        provider=provider_name,
        model=model_name,
        base_url=_redact_base_url(base_url_text),
        api_key_env=api_key_env_name,
        api_key_present=has_api_key,
        network_check_allowed=network_allowed,
        network_check_requested=perform_network_check,
        network_check_executed=network_check_executed,
        checks=checks,
        warnings=warnings,
        errors=errors,
        latency_ms=network_latency_ms,
    )
