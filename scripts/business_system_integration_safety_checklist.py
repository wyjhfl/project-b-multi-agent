from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_integration_safety"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

OPT_IN_KEYS = [
    "BUSINESS_INTEGRATION_ENABLED",
    "BUSINESS_INTEGRATION_READ_ONLY",
    "BUSINESS_INTEGRATION_WRITE_ENABLED",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
]
CONFIG_KEYS = [
    "BUSINESS_SYSTEM_NAME",
    "BUSINESS_SYSTEM_BASE_URL_ENV",
    "BUSINESS_SYSTEM_TOKEN_ENV",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
]
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)https?://[^/\s:]+:[^@\s]+@[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]
BOUNDARY_DECLARATIONS = [
    "只读 Business system integration safety checklist。",
    "仅检查 opt-in 配置、本地代码文件和测试文件存在性。",
    "不连接真实业务系统，不执行真实业务读写，不创建、更新或删除业务数据。",
    "真实业务工具必须经过 ToolGateway、PolicyEngine、审批链路和审计链路。",
    "不读取或输出真实 token、API key、client_secret、连接串密码或业务系统 URL 原文。",
    "写入集成必须显式 opt-in，并具备审批、审计、幂等、回滚和失败恢复证据。",
    "不宣称真实业务系统生产集成验收完成。",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _env_presence(keys: list[str]) -> dict[str, dict[str, Any]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _target_env_presence(env_name_key: str) -> dict[str, Any]:
    env_name = (os.getenv(env_name_key, "") or "").strip()
    return {
        "env_name_key": env_name_key,
        "env_name": env_name,
        "present": bool(env_name and os.getenv(env_name)),
    }


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _local_checks() -> dict[str, dict[str, Any]]:
    paths = {
        "tool_gateway": "app/harness/gateway/tool_gateway.py",
        "policy_engine": "app/harness/policy/engine.py",
        "operation_whitelist": "app/harness/policy/operation_whitelist.py",
        "approval_store": "app/storage/approval_store.py",
        "approval_api": "app/api/approvals.py",
        "approval_resume_service": "app/services/approval_resume.py",
        "audit_store": "app/storage/audit_store.py",
        "audit_recorder": "app/harness/audit/recorder.py",
        "audit_api": "app/api/audit.py",
        "multi_tool_pipeline": "app/services/multitool_pipeline.py",
        "request_guards": "app/core/request_guards.py",
        "guardrails": "app/harness/security/guardrails.py",
        "injection_guard": "app/harness/security/injection_guard.py",
        "tool_gateway_tests": "tests/test_mcp_gateway_v03.py",
        "security_tests": "tests/test_security_v04.py",
        "audit_tests": "tests/test_audit_v045.py",
        "approval_resume_tests": "tests/test_approval_resume_v042.py",
        "full_resume_tests": "tests/test_v043_full_resume.py",
        "request_guard_tests": "tests/test_request_guards_v72.py",
    }
    return {key: {"path": path, "present": _path_exists(path)} for key, path in paths.items()}


def _missing_local(local: dict[str, dict[str, Any]], keys: list[str]) -> list[str]:
    return [f"local:{key}" for key in keys if not local.get(key, {}).get("present")]


def _check(
    check_id: str,
    *,
    status: str,
    missing_conditions: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    risk_notes: list[str] | None = None,
    recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "missing_conditions": sorted(set(missing_conditions or [])),
        "evidence": evidence or {},
        "risk_notes": risk_notes or [],
        "recommended_actions": recommended_actions or [],
    }


def _acceptance_checks(local: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    integration_enabled = _env_enabled("BUSINESS_INTEGRATION_ENABLED")
    read_only = _env_enabled("BUSINESS_INTEGRATION_READ_ONLY")
    write_enabled = _env_enabled("BUSINESS_INTEGRATION_WRITE_ENABLED")
    approval_required = _env_enabled("BUSINESS_INTEGRATION_APPROVAL_REQUIRED")
    audit_required = _env_enabled("BUSINESS_INTEGRATION_AUDIT_REQUIRED")
    tool_allowlist = _parse_csv(os.getenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST"))
    write_tool_allowlist = _parse_csv(os.getenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST"))
    timeout_present = bool(os.getenv("BUSINESS_SYSTEM_TIMEOUT_SECONDS"))

    gateway_required = ["tool_gateway", "policy_engine", "operation_whitelist", "multi_tool_pipeline", "tool_gateway_tests"]
    approval_files = ["approval_store", "approval_api", "approval_resume_service", "approval_resume_tests", "full_resume_tests"]
    audit_files = ["audit_store", "audit_recorder", "audit_api", "audit_tests"]
    safety_files = ["guardrails", "injection_guard", "request_guards", "security_tests", "request_guard_tests"]

    return [
        _check(
            "business_integration_opt_in",
            status="partial" if integration_enabled and read_only else "skipped",
            missing_conditions=(
                ([] if integration_enabled else ["opt_in:BUSINESS_INTEGRATION_ENABLED_not_enabled"])
                + ([] if read_only else ["opt_in:BUSINESS_INTEGRATION_READ_ONLY_not_enabled"])
            ),
            evidence={
                "env": _env_presence(OPT_IN_KEYS + CONFIG_KEYS),
                "base_url_target": _target_env_presence("BUSINESS_SYSTEM_BASE_URL_ENV"),
                "token_target": _target_env_presence("BUSINESS_SYSTEM_TOKEN_ENV"),
                "business_system_connected": False,
                "business_read_executed": False,
                "business_write_executed": False,
            },
        ),
        _check(
            "tool_gateway_policy_boundary",
            status="partial" if not _missing_local(local, gateway_required) else "skipped",
            missing_conditions=_missing_local(local, gateway_required),
            evidence={key: local[key] for key in gateway_required if key in local},
        ),
        _check(
            "tool_allowlist_and_timeout",
            status="partial" if tool_allowlist and timeout_present else "skipped",
            missing_conditions=(
                ([] if tool_allowlist else ["env:BUSINESS_SYSTEM_TOOL_ALLOWLIST"])
                + ([] if timeout_present else ["env:BUSINESS_SYSTEM_TIMEOUT_SECONDS"])
            ),
            evidence={
                "tool_allowlist_present": bool(tool_allowlist),
                "tool_allowlist_count": len(tool_allowlist),
                "timeout_configured": timeout_present,
            },
        ),
        _check(
            "write_boundary_and_idempotency",
            status="partial" if write_enabled and write_tool_allowlist and approval_required and audit_required else "skipped",
            missing_conditions=(
                ([] if write_enabled else ["opt_in:BUSINESS_INTEGRATION_WRITE_ENABLED_not_enabled"])
                + ([] if write_tool_allowlist else ["env:BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST"])
                + ([] if approval_required else ["opt_in:BUSINESS_INTEGRATION_APPROVAL_REQUIRED_not_enabled"])
                + ([] if audit_required else ["opt_in:BUSINESS_INTEGRATION_AUDIT_REQUIRED_not_enabled"])
            ),
            evidence={
                "write_tool_allowlist_present": bool(write_tool_allowlist),
                "write_tool_allowlist_count": len(write_tool_allowlist),
                "approval_required": approval_required,
                "audit_required": audit_required,
                "business_write_executed": False,
            },
        ),
        _check(
            "approval_resume_boundary",
            status="partial" if not _missing_local(local, approval_files) else "skipped",
            missing_conditions=_missing_local(local, approval_files),
            evidence={key: local[key] for key in approval_files if key in local},
        ),
        _check(
            "audit_evidence_boundary",
            status="partial" if not _missing_local(local, audit_files) else "skipped",
            missing_conditions=_missing_local(local, audit_files),
            evidence={key: local[key] for key in audit_files if key in local},
        ),
        _check(
            "request_guard_and_prompt_safety",
            status="partial" if not _missing_local(local, safety_files) else "skipped",
            missing_conditions=_missing_local(local, safety_files),
            evidence={key: local[key] for key in safety_files if key in local},
        ),
        _check(
            "failure_recovery_and_rollback_evidence",
            status="skipped",
            missing_conditions=["evidence:rollback_runbook_not_provided", "evidence:failure_recovery_drill_not_provided"],
            evidence={
                "rollback_executed": False,
                "failure_recovery_executed": False,
                "business_system_connected": False,
            },
        ),
    ]


def _derive_status(checks: list[dict[str, Any]], local: dict[str, dict[str, Any]]) -> str:
    if any(check["status"] == "blocked" for check in checks):
        return "blocked"
    if any(not item["present"] for item in local.values()):
        return "skipped"
    if any(check["status"] == "skipped" for check in checks):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.7 Business system integration safety checklist（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- business_system_connected: {payload.get('business_system_connected', False)}",
        f"- business_read_executed: {payload.get('business_read_executed', False)}",
        f"- business_write_executed: {payload.get('business_write_executed', False)}",
        "",
        "## 检查项",
    ]
    for check in payload.get("acceptance_checks", []):
        lines.extend(
            [
                f"### {check['check_id']}",
                f"- status: {check['status']}",
                f"- missing_conditions: {json.dumps(check.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_business_system_integration_safety_checklist(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    local = _local_checks()
    checks = _acceptance_checks(local)
    missing_conditions = sorted({item for check in checks for item in check.get("missing_conditions", [])})
    status = _derive_status(checks, local)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.7.0",
        "phase": "v3.7 Phase 17.5",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "business_system_connected": False,
        "business_read_executed": False,
        "business_write_executed": False,
        "business_data_written": False,
        "approval_bypassed": False,
        "audit_bypassed": False,
        "secret_plaintext_output": False,
        "env": _env_presence(OPT_IN_KEYS + CONFIG_KEYS),
        "base_url_target": _target_env_presence("BUSINESS_SYSTEM_BASE_URL_ENV"),
        "token_target": _target_env_presence("BUSINESS_SYSTEM_TOKEN_ENV"),
        "local_checks": local,
        "acceptance_checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }
    if _contains_secret_like_text(json.dumps(payload, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_business_system_integration_safety"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "business_system_connected": False,
        "business_read_executed": False,
        "business_write_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "check_count": len(checks),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.7 Business system integration safety checklist（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_business_system_integration_safety_checklist(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
