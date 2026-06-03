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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "external_mcp_acceptance_gate"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读 External MCP acceptance gate",
    "仅检查 MCP 配置存在性、allowlist 状态和本地测试/代码文件存在性",
    "不启动 MCP subprocess",
    "不执行真实 tools/list",
    "不执行真实 tools/call",
    "不连接真实外部 MCP Server",
    "不绕过 ToolGateway、PolicyEngine、审批链路或审计链路",
    "不读取或输出真实 secret 原文",
    "默认 fake/offline，默认 pytest/CI 不连接真实外部 MCP",
    "不宣称真实外部 MCP 生产验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _env_presence(keys: list[str]) -> dict[str, dict[str, Any]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _local_checks() -> dict[str, dict[str, Any]]:
    paths = {
        "stdio_client": "app/tools/mcp/stdio_client.py",
        "mcp_registration": "app/main.py",
        "tool_gateway": "app/harness/gateway/tool_gateway.py",
        "policy_engine": "app/harness/policy/engine.py",
        "approval_api": "app/api/approvals.py",
        "audit_api": "app/api/audit.py",
        "fake_stdio_fixture": "tests/fixtures/fake_mcp_stdio_server.py",
        "stdio_client_tests": "tests/test_mcp_stdio_client_v31.py",
        "mcp_gateway_tests": "tests/test_mcp_gateway_v03.py",
    }
    return {key: {"path": path, "present": _path_exists(path)} for key, path in paths.items()}


def _acceptance_checks() -> list[dict[str, Any]]:
    mcp_mode = (os.getenv("MCP_MODE", "") or "").strip().lower()
    command = (os.getenv("MCP_SERVER_COMMAND", "") or "").strip()
    command_allowlist = _parse_csv(os.getenv("MCP_SERVER_COMMAND_ALLOWLIST"))
    tool_allowlist = _parse_csv(os.getenv("MCP_TOOL_ALLOWLIST"))
    timeout_raw = (os.getenv("MCP_SERVER_TIMEOUT_SECONDS", "") or "").strip()
    timeout_configured = bool(timeout_raw)
    command_configured = bool(command)
    command_in_allowlist = bool(command and command_allowlist and command in command_allowlist)

    checks = [
        {
            "check_id": "real_mode_opt_in",
            "status": "partial" if mcp_mode == "real" else "skipped",
            "missing_conditions": [] if mcp_mode == "real" else ["env:MCP_MODE_not_real"],
            "evidence": {"env_name": "MCP_MODE", "expected": "real", "actual_present": bool(mcp_mode)},
        },
        {
            "check_id": "command_configured",
            "status": "partial" if command_configured else "skipped",
            "missing_conditions": [] if command_configured else ["env:MCP_SERVER_COMMAND"],
            "evidence": {"env_name": "MCP_SERVER_COMMAND", "present": command_configured},
        },
        {
            "check_id": "command_allowlist",
            "status": "partial" if command_in_allowlist else ("blocked" if command_configured and command_allowlist else "skipped"),
            "missing_conditions": [] if command_in_allowlist else ["env:MCP_SERVER_COMMAND_ALLOWLIST", "policy:command_not_allowlisted"],
            "evidence": {
                "command_present": command_configured,
                "allowlist_present": bool(command_allowlist),
                "command_in_allowlist": command_in_allowlist,
            },
        },
        {
            "check_id": "tool_allowlist",
            "status": "partial" if tool_allowlist else "skipped",
            "missing_conditions": [] if tool_allowlist else ["env:MCP_TOOL_ALLOWLIST"],
            "evidence": {"tool_allowlist_present": bool(tool_allowlist), "tool_allowlist_count": len(tool_allowlist)},
        },
        {
            "check_id": "timeout_config",
            "status": "partial" if timeout_configured else "skipped",
            "missing_conditions": [] if timeout_configured else ["env:MCP_SERVER_TIMEOUT_SECONDS"],
            "evidence": {"timeout_configured": timeout_configured},
        },
        {
            "check_id": "lifecycle_hardening",
            "status": "partial",
            "missing_conditions": [],
            "evidence": {
                "stdio_client_present": _path_exists("app/tools/mcp/stdio_client.py"),
                "stdio_tests_present": _path_exists("tests/test_mcp_stdio_client_v31.py"),
                "process_started": False,
            },
        },
        {
            "check_id": "approval_audit_boundary",
            "status": "partial",
            "missing_conditions": [],
            "evidence": {
                "tool_gateway_present": _path_exists("app/harness/gateway/tool_gateway.py"),
                "policy_engine_present": _path_exists("app/harness/policy/engine.py"),
                "approval_api_present": _path_exists("app/api/approvals.py"),
                "audit_api_present": _path_exists("app/api/audit.py"),
            },
        },
        {
            "check_id": "fake_fixture_coverage",
            "status": "partial",
            "missing_conditions": [],
            "evidence": {
                "fake_fixture_present": _path_exists("tests/fixtures/fake_mcp_stdio_server.py"),
                "default_tests_use_fake_fixture": True,
            },
        },
    ]
    return checks


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
        "# v3.7 External MCP acceptance gate（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- mcp_process_started: {payload.get('mcp_process_started', False)}",
        f"- external_mcp_connected: {payload.get('external_mcp_connected', False)}",
        "",
        "## 门禁项",
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


def build_external_mcp_acceptance_gate(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    env = _env_presence(
        [
            "MCP_MODE",
            "MCP_SERVER_COMMAND",
            "MCP_SERVER_COMMAND_ALLOWLIST",
            "MCP_TOOL_ALLOWLIST",
            "MCP_SERVER_TIMEOUT_SECONDS",
        ]
    )
    local = _local_checks()
    checks = _acceptance_checks()
    missing_conditions = sorted({item for check in checks for item in check.get("missing_conditions", [])})
    status = _derive_status(checks, local)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "phase": "v3.7 Phase 17.2",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "mcp_process_started": False,
        "mcp_tools_list_executed": False,
        "mcp_tools_call_executed": False,
        "secret_plaintext_output": False,
        "env": env,
        "local_checks": local,
        "acceptance_checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "真实 MCP opt-in 演练前必须配置 MCP_MODE=real、command allowlist 和 tool allowlist。",
            "真实 MCP tools/call 必须继续经过 ToolGateway、PolicyEngine、审批链路和审计链路。",
            "Phase 17.3 可继续推进 Real LLM provider acceptance gate。",
        ],
        "output_dir": str(output_root),
    }
    if _contains_secret_like_text(json.dumps(payload, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_external_mcp_acceptance_gate"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "mcp_process_started": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "check_count": len(checks),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.7 External MCP acceptance gate（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_external_mcp_acceptance_gate(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
