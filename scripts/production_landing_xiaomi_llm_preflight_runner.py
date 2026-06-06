from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Iterator

from app.core.config import settings
from app.harness.llm.preflight import run_llm_provider_preflight

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight"
XIAOMI_API_KEY_ENV = "XIAOMI_LLM_API_KEY"
XIAOMI_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
XIAOMI_MODEL = "mimo-v2.5-pro"

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like_text(key) or _contains_secret_like_text(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like_text(item) for item in value)
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like_text(value) else value
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _is_present_non_placeholder(value: str | None) -> bool:
    text = (value or "").strip()
    return bool(text and not (text.startswith("<") and text.endswith(">")))


def _safe_base_url_host(value: str) -> str:
    parsed = urlparse(value)
    return parsed.netloc or ""


def _build_acceptance_blockers(
    *,
    api_key_present: bool,
    network_requested: bool,
    network_allowed: bool,
    network_executed: bool,
    status: str,
) -> list[str]:
    blockers: list[str] = []
    if not api_key_present:
        blockers.append("missing_process_env:XIAOMI_LLM_API_KEY")
    if not network_requested:
        blockers.append("network_check_not_requested")
    if network_requested and not network_allowed:
        blockers.append("network_check_not_allowed_without_process_key")
    if network_allowed and not network_executed:
        blockers.append("network_check_not_executed")
    if status not in {"success"}:
        blockers.append(f"preflight_status_not_success:{status}")
    return sorted(set(blockers))


def _safe_next_action(*, api_key_present: bool, network_requested: bool, status: str) -> str:
    if status == "success":
        return "refresh_landing_status_and_continue_manual_signoff"
    if not api_key_present:
        return "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    if not network_requested:
        return "rerun_with_execute_network_check"
    return "inspect_preflight_errors_and_retry_after_provider_or_network_fix"


@contextmanager
def _temporary_xiaomi_settings(*, network_check: bool, timeout_seconds: float) -> Iterator[None]:
    patch = {
        "real_llm_acceptance_enabled": True,
        "real_llm_preflight_enabled": True,
        "real_llm_provider": "litellm",
        "real_llm_model": XIAOMI_MODEL,
        "real_llm_base_url": XIAOMI_BASE_URL,
        "real_llm_api_key_env": XIAOMI_API_KEY_ENV,
        "real_llm_preflight_network_check": bool(network_check),
        "real_llm_preflight_timeout_seconds": float(timeout_seconds),
        "llm_timeout_seconds": min(max(float(timeout_seconds), 1.0), 300.0),
        "llm_max_retries": 0,
        "llm_retry_backoff_seconds": 0.0,
    }
    previous = {key: getattr(settings, key) for key in patch}
    try:
        for key, value in patch.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)


def _safe_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "name": str(item.get("name") or ""),
                "ok": bool(item.get("ok", False)),
                "detail": _redact_value(str(item.get("detail") or "")),
            }
        )
    return safe


def build_production_landing_xiaomi_llm_preflight_runner(
    *,
    output_dir: str | Path | None = None,
    execute_network_check: bool = False,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    api_key_present = _is_present_non_placeholder(os.getenv(XIAOMI_API_KEY_ENV))
    network_requested = bool(execute_network_check)
    network_allowed = network_requested and api_key_present
    status = "skipped"
    result_payload: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []

    if not api_key_present:
        warnings.append("missing_process_env:XIAOMI_LLM_API_KEY")
    elif not network_requested:
        warnings.append("network_check_not_requested")
        with _temporary_xiaomi_settings(network_check=False, timeout_seconds=timeout_seconds):
            result = run_llm_provider_preflight(perform_network_check=False)
        result_payload = result.to_dict()
        status = "partial" if result_payload.get("status") == "ready" else "failed"
    else:
        with _temporary_xiaomi_settings(network_check=True, timeout_seconds=timeout_seconds):
            result = run_llm_provider_preflight(perform_network_check=True)
        result_payload = result.to_dict()
        status = "success" if result_payload.get("status") == "passed" else "failed"
        errors.extend(str(item) for item in result_payload.get("errors", []) if isinstance(item, str))
        warnings.extend(str(item) for item in result_payload.get("warnings", []) if isinstance(item, str))

    safe_result = {
        "preflight_status": str(result_payload.get("status") or ""),
        "allowed": bool(result_payload.get("allowed", False)),
        "provider": str(result_payload.get("provider") or "litellm"),
        "model": XIAOMI_MODEL,
        "base_url": XIAOMI_BASE_URL,
        "base_url_host": _safe_base_url_host(XIAOMI_BASE_URL),
        "provider_endpoint_kind": "openai_compatible_chat_completions",
        "api_key_env": XIAOMI_API_KEY_ENV,
        "api_key_present": api_key_present,
        "network_check_requested": network_requested,
        "network_check_allowed": network_allowed,
        "network_check_executed": bool(result_payload.get("network_check_executed", False)),
        "timeout_seconds": float(timeout_seconds),
        "latency_ms": float(result_payload.get("latency_ms", 0.0) or 0.0),
        "checks": _safe_checks(result_payload.get("checks", []) if isinstance(result_payload.get("checks"), list) else []),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    acceptance_blockers = _build_acceptance_blockers(
        api_key_present=api_key_present,
        network_requested=network_requested,
        network_allowed=network_allowed,
        network_executed=bool(safe_result["network_check_executed"]),
        status=status,
    )
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.0",
        "phase": "v4.7 Xiaomi Real LLM Preflight Runner",
        "status": status,
        "mode": "process_env_only_preflight",
        "env_file_written": False,
        "local_env_modified": False,
        "api_key_env": XIAOMI_API_KEY_ENV,
        "api_key_present": api_key_present,
        "real_llm_model": XIAOMI_MODEL,
        "real_llm_base_url": XIAOMI_BASE_URL,
        "execute_network_check": network_requested,
        "preflight": safe_result,
        "acceptance_blockers": acceptance_blockers,
        "safe_next_action": _safe_next_action(
            api_key_present=api_key_present,
            network_requested=network_requested,
            status=status,
        ),
        "warnings": sorted(set(_redact_value(warnings))),
        "errors": sorted(set(_redact_value(errors))),
        "next_commands": [
            "python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check",
            "python scripts/production_landing_env_check.py",
            "python scripts/production_landing_execution_gate.py",
        ],
        "real_llm_executed": bool(safe_result["network_check_executed"] and status == "success"),
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = True
        payload["errors"] = sorted(set([*payload["errors"], "secret_like_output_detected"]))

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_xiaomi_llm_preflight"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "api_key_present": api_key_present,
        "real_llm_executed": payload["real_llm_executed"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    preflight = payload.get("preflight", {}) if isinstance(payload.get("preflight"), dict) else {}
    lines = [
        "# Xiaomi Real LLM Preflight Runner",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- env_file_written: {payload.get('env_file_written', False)}",
        f"- api_key_env: {payload.get('api_key_env', '')}",
        f"- api_key_present: {payload.get('api_key_present', False)}",
        f"- real_llm_model: {payload.get('real_llm_model', '')}",
        f"- execute_network_check: {payload.get('execute_network_check', False)}",
        f"- network_check_executed: {preflight.get('network_check_executed', False)}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        f"- safe_next_action: {payload.get('safe_next_action', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Acceptance Blockers",
    ]
    lines.extend(f"- {item}" for item in payload.get("acceptance_blockers", []))
    lines.extend([
        "",
        "## Warnings",
    ])
    lines.extend(f"- {item}" for item in payload.get("warnings", []))
    lines.extend(["", "## Errors"])
    lines.extend(f"- {item}" for item in payload.get("errors", []))
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Xiaomi OpenAI-compatible real LLM preflight without writing secrets to files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute-network-check", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_xiaomi_llm_preflight_runner(
        output_dir=args.output_dir,
        execute_network_check=args.execute_network_check,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
