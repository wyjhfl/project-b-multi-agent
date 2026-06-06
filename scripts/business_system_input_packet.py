from __future__ import annotations

import argparse
import json
import os
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

from app.integrations.business_system import load_business_system_config, safe_config_summary

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_input_packet"

OWNER_ENV = {
    "business_owner": "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "security_reviewer": "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "operations_owner": "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "data_owner": "BUSINESS_SYSTEM_DATA_OWNER",
}

LOCAL_ENV_TEMPLATE_LINES = [
    "BUSINESS_INTEGRATION_ENABLED=true",
    "BUSINESS_INTEGRATION_READ_ONLY=true",
    "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
    "BUSINESS_SYSTEM_NAME=<system-name>",
    "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
    "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _present(env_key: str) -> bool:
    return bool((os.getenv(env_key, "") or "").strip())


def _missing_conditions() -> list[str]:
    config = load_business_system_config()
    missing: list[str] = []
    for owner_name, env_key in OWNER_ENV.items():
        if not _present(env_key):
            missing.append(f"owner:{owner_name}_missing")
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
        missing.append("env:BUSINESS_SYSTEM_BASE_URL_ENV_missing")
    elif not config.base_url_present:
        missing.append("env_target:BUSINESS_SYSTEM_BASE_URL_missing")
    if not config.token_env:
        missing.append("env:BUSINESS_SYSTEM_TOKEN_ENV_missing")
    elif not config.token_present:
        missing.append("env_target:BUSINESS_SYSTEM_TOKEN_missing")
    if not config.read_probe_path:
        missing.append("env:BUSINESS_SYSTEM_READ_PROBE_PATH_missing")
    if not config.auth_header_name:
        missing.append("env:BUSINESS_SYSTEM_AUTH_HEADER_NAME_missing")
    return sorted(set(missing))


def _owner_safety_conditions() -> list[str]:
    unsafe: list[str] = []
    for owner_name, env_key in OWNER_ENV.items():
        value = os.getenv(env_key, "") or ""
        if _contains_secret_like(value):
            unsafe.append(f"owner:{owner_name}_secret_like")
    return unsafe


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    lowered = text.lower()
    if "sk-" in lowered or "bearer " in lowered:
        return True
    safe_placeholders = {"<secret-managed-token>", "<set-in-local-env-only>", "<owner-or-staff-id>"}
    for marker in ("token=", "api_key=", "password=", "client_secret=", "business_system_token="):
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
            normalized = raw_value.strip().lower()
            if normalized and normalized not in safe_placeholders:
                return True
            start = index + len(marker)
    return False


def _redact_secret_like(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(_redact_secret_like(key)): _redact_secret_like(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_secret_like(item) for item in value]
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    return value


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 业务系统真实接入输入准备包",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_real_read_smoke: {payload.get('ready_for_real_read_smoke', False)}",
        f"- missing_condition_count: {payload.get('missing_condition_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 缺口",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## 本地进程环境模板"])
    for line in payload.get("local_env_template_lines", []):
        lines.append(f"- `{line}`")
    lines.extend(["", "## 人工输入检查清单"])
    for item in payload.get("manual_input_checklist", []):
        lines.append(f"- {item.get('id')}: {item.get('description')} env={item.get('env', [])}")
    lines.extend(["", "## 推荐命令"])
    for command in payload.get("recommended_commands", []):
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## 安全边界",
            "- 本包只检查环境变量存在性，不读取或输出 URL/token 原文。",
            "- 真实 smoke 必须通过只读 token 执行，并保持业务写入 false。",
            "- public_production_direct_launch 必须保持 No-Go。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_business_system_input_packet"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def build_business_system_input_packet(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    config = load_business_system_config()
    owner_safety = _owner_safety_conditions()
    missing = sorted(set(_missing_conditions() + owner_safety))
    owner_inputs_present = {name: _present(env_key) for name, env_key in OWNER_ENV.items()}
    ready = not missing
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.21",
        "phase": "v4.8 Business System Real Input Packet",
        "status": "ready" if ready else "needs_input",
        "read_only": True,
        "ready_for_real_read_smoke": ready,
        "owner_inputs_present": owner_inputs_present,
        "config": safe_config_summary(config),
        "missing_conditions": missing,
        "missing_condition_count": len(missing),
        "required_inputs": [
            {
                "id": "business_owner_chain",
                "env": list(OWNER_ENV.values()),
                "description": "业务、数据、安全、运维四类负责人标识。",
            },
            {
                "id": "business_system_read_only_endpoint",
                "env": ["BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL", "BUSINESS_SYSTEM_READ_PROBE_PATH"],
                "description": "真实业务系统只读健康或探测端点。",
            },
            {
                "id": "business_system_read_only_token",
                "env": ["BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN"],
                "description": "当前进程或外部 secret manager 注入的只读 token。",
            },
        ],
        "local_env_template_lines": LOCAL_ENV_TEMPLATE_LINES,
        "manual_input_checklist": [
            {
                "id": "owners",
                "env": list(OWNER_ENV.values()),
                "description": "填写负责人名称或工号，不填写 token、连接串或 URL。",
            },
            {
                "id": "endpoint",
                "env": ["BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL", "BUSINESS_SYSTEM_READ_PROBE_PATH"],
                "description": "只读探测 URL 通过进程环境或 secret manager 注入，报告只输出 present 布尔值。",
            },
            {
                "id": "credential",
                "env": ["BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN"],
                "description": "只读 token 仅进入当前进程环境，不提交、不写报告、不打印。",
            },
            {
                "id": "safety_switches",
                "env": [
                    "BUSINESS_INTEGRATION_READ_ONLY",
                    "BUSINESS_INTEGRATION_WRITE_ENABLED",
                    "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
                    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
                ],
                "description": "必须保持 read-only=true、write=false、只 allowlist business_read_probe。",
            },
        ],
        "recommended_commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -PreflightOnly -EnvPath local\\production_landing.staging.env",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -EnvPath local\\production_landing.staging.env",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_landing_resume.ps1 -UseExistingEnv",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\business_system_production_readiness_brief.py",
        ],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
        "output_dir": str(output_root),
    }
    if owner_safety or _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["ready_for_real_read_smoke"] = False
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["boundary:secret_like_text_detected"]))
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload = _redact_secret_like(payload)
    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "ready_for_real_read_smoke": payload["ready_for_real_read_smoke"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
        "public_production_direct_launch": "No-Go",
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成业务系统真实接入输入准备包。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_business_system_input_packet(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready", "needs_input", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
