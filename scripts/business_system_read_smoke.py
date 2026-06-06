from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.policy.operation_whitelist import OperationWhitelist
from app.integrations.business_system import (
    load_business_system_config,
    redact_secret_like,
    register_business_system_tools,
    safe_config_summary,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    lowered = text.lower()
    if "sk-" in lowered or "bearer " in lowered:
        return True
    for marker in ("token=", "api_key=", "password=", "client_secret="):
        start = 0
        while True:
            index = lowered.find(marker, start)
            if index < 0:
                break
            raw_tail = text[index + len(marker) :]
            raw_value = ""
            for char in raw_tail:
                if char.isspace() or char in {",", "]", "}", "\"", "'", ";"}:
                    break
                raw_value += char
            normalized = raw_value.strip("<>").lower()
            if normalized and normalized not in {"secret-managed-token", "set-in-local-env-only"}:
                return True
            start = index + len(marker)
    return False


def _missing_conditions(execute: bool) -> list[str]:
    config = load_business_system_config()
    missing: list[str] = []
    if not execute:
        missing.append("cli:--execute_not_requested")
    if not config.enabled:
        missing.append("opt_in:BUSINESS_INTEGRATION_ENABLED_not_enabled")
    if not config.read_only:
        missing.append("opt_in:BUSINESS_INTEGRATION_READ_ONLY_not_enabled")
    if config.write_enabled:
        missing.append("opt_in:BUSINESS_INTEGRATION_WRITE_ENABLED_must_be_false")
    if not config.approval_required:
        missing.append("opt_in:BUSINESS_INTEGRATION_APPROVAL_REQUIRED_not_enabled")
    if not config.audit_required:
        missing.append("opt_in:BUSINESS_INTEGRATION_AUDIT_REQUIRED_not_enabled")
    if "business_read_probe" not in config.tool_allowlist:
        missing.append("env:BUSINESS_SYSTEM_TOOL_ALLOWLIST_missing_business_read_probe")
    if config.write_tool_allowlist:
        missing.append("env:BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST_must_be_empty")
    if not config.base_url_env:
        missing.append("env:BUSINESS_SYSTEM_BASE_URL_ENV")
    elif not config.base_url_present:
        missing.append("env_target:BUSINESS_SYSTEM_BASE_URL_ENV_missing")
    if not config.token_env:
        missing.append("env:BUSINESS_SYSTEM_TOKEN_ENV")
    elif not config.token_present:
        missing.append("env_target:BUSINESS_SYSTEM_TOKEN_ENV_missing")
    return sorted(set(missing))


def _execute_smoke() -> dict[str, Any]:
    config = load_business_system_config()
    gateway = ToolGateway()
    specs = register_business_system_tools(gateway, config)
    policy = PolicyEngine(OperationWhitelist(gateway))
    decision = policy.evaluate(
        "business_read_probe",
        risk_level=specs[0].risk_level if specs else None,
        context={"mode": "keyword", "permission_scope": "read"},
    )
    if not specs:
        return {
            "status": "failed",
            "tool_registered": False,
            "policy_allowed": False,
            "gateway_call_success": False,
            "error": "business_read_probe_not_registered",
        }
    if not decision.get("allowed"):
        return {
            "status": "blocked",
            "tool_registered": True,
            "policy_allowed": False,
            "gateway_call_success": False,
            "policy_reason": decision.get("reason", ""),
        }
    record = gateway.call("business_read_probe", {})
    return {
        "status": "success" if record.success else "failed",
        "tool_registered": True,
        "policy_allowed": True,
        "gateway_call_success": bool(record.success),
        "latency_ms": record.latency_ms,
        "result": redact_secret_like(record.result),
        "error": record.error,
    }


def _env_profile(config: Any, execute: bool, missing: list[str]) -> dict[str, Any]:
    auth_mode = "bearer" if config.auth_header_name.lower() == "authorization" and config.auth_scheme else "api_key_header"
    return {
        "execution_requested": execute,
        "ready_for_execute": execute and not missing,
        "required_env": [
            "BUSINESS_INTEGRATION_ENABLED=true",
            "BUSINESS_INTEGRATION_READ_ONLY=true",
            "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
            "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
            "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
            "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
            "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
            "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
            "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
            "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
            "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
            "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
            "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
            "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
        ],
        "auth_mode": auth_mode,
        "safe_commands": {
            "interactive_powershell": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
            "api_key_header": 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -AuthHeaderName X-API-Key -AuthScheme ""',
            "existing_secret_manager_env": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv",
        },
        "present": {
            "enabled": config.enabled,
            "read_only": config.read_only,
            "write_enabled": config.write_enabled,
            "approval_required": config.approval_required,
            "audit_required": config.audit_required,
            "base_url_env": bool(config.base_url_env),
            "base_url_value": config.base_url_present,
            "token_env": bool(config.token_env),
            "token_value": config.token_present,
            "read_probe_allowlisted": "business_read_probe" in config.tool_allowlist,
            "write_tool_allowlist_empty": len(config.write_tool_allowlist) == 0,
            "auth_header_configured": bool(config.auth_header_name),
            "auth_scheme_configured": bool(config.auth_scheme),
        },
        "public_production_gap": not (execute and not missing),
        "next_action": "在本地进程环境或外部 secret manager 注入真实只读 URL/token 后执行安全 PowerShell 入口。",
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    env_profile = payload.get("env_profile") if isinstance(payload.get("env_profile"), dict) else {}
    lines = [
        "# 业务系统只读 Smoke 报告",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute: {payload.get('execute', False)}",
        f"- local_business_mock_used: {payload.get('local_business_mock_used', False)}",
        f"- business_system_connected: {payload.get('business_system_connected', False)}",
        f"- business_read_executed: {payload.get('business_read_executed', False)}",
        f"- business_write_executed: {payload.get('business_write_executed', False)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 执行前置检查",
        f"- ready_for_execute: {env_profile.get('ready_for_execute', False)}",
        f"- auth_mode: {env_profile.get('auth_mode', '')}",
        f"- public_production_gap: {env_profile.get('public_production_gap', True)}",
        "",
        "## 边界",
        "- 默认不连接真实业务系统；必须显式 --execute 并满足环境 opt-in。",
        "- 仅注册 business_read_probe 只读工具，并通过 ToolGateway 与 PolicyEngine 调用。",
        "- 不执行业务写入，不绕过审批或审计边界，不输出 token/base URL 原文。",
        "",
    ]
    return "\n".join(lines)


def build_business_system_env_template(*, output_path: str | Path) -> dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Business system read-only smoke template",
        "# Fill values in a local .env or current process only. Do not commit real URL/token values.",
        "BUSINESS_INTEGRATION_ENABLED=true",
        "BUSINESS_INTEGRATION_READ_ONLY=true",
        "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
        "BUSINESS_SYSTEM_NAME=<system-name>",
        "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
        "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
        "BUSINESS_SYSTEM_BASE_URL=<https://business-system.example.com>",
        "BUSINESS_SYSTEM_TOKEN=<set-in-local-env-only>",
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
        "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
        "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
        "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
        "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
        "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
        "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "success",
        "template_path": str(path),
        "secret_plaintext_output": False,
        "business_write_enabled": False,
    }


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_business_system_read_smoke"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def build_business_system_read_smoke(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
    local_business_mock_used: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    config = load_business_system_config()
    missing = _missing_conditions(execute)

    smoke: dict[str, Any] = {}
    if missing:
        status = "skipped" if not execute else "blocked"
    else:
        smoke = _execute_smoke()
        status = str(smoke.get("status") or "failed")
    read_succeeded = bool(status == "success" and smoke.get("gateway_call_success") is True)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.3",
        "phase": "v4.5 Phase 25.5 Business System Read Smoke",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "execute": execute,
        "execution_requested": execute,
        "local_business_mock_used": local_business_mock_used,
        "read_only": True,
        "config": safe_config_summary(config),
        "env_profile": _env_profile(config, execute, missing),
        "missing_conditions": missing,
        "smoke": smoke,
        "business_system_connected": status == "success",
        "business_read_executed": read_succeeded,
        "business_write_executed": False,
        "business_data_written": False,
        "approval_bypassed": False,
        "audit_bypassed": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "business_system_read_smoke": "Manual-Review" if status == "success" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": str(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "execute": execute,
        "local_business_mock_used": local_business_mock_used,
        "business_system_connected": payload["business_system_connected"],
        "business_read_executed": payload["business_read_executed"],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "output_dir": str(output_root),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成业务系统只读 smoke 证据。默认不连接真实业务系统。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="执行受控只读业务系统探测。")
    parser.add_argument("--write-env-template", default=None, help="写出业务系统只读 smoke 环境变量模板。")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.write_env_template:
        summary = build_business_system_env_template(output_path=args.write_env_template)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    summary = build_business_system_read_smoke(output_dir=args.output_dir, execute=args.execute)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
