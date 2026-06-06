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


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    lowered = text.lower()
    if "sk-" in lowered or "bearer " in lowered:
        return True
    for marker in ("token=", "api_key=", "password=", "client_secret=", "business_system_token="):
        if marker in lowered:
            return True
    return False


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
    missing = _missing_conditions()
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
        "recommended_commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\business_system_production_readiness_brief.py",
        ],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
        "output_dir": str(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["ready_for_real_read_smoke"] = False
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["boundary:secret_like_text_detected"]))
        payload["missing_condition_count"] = len(payload["missing_conditions"])
    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "ready_for_real_read_smoke": payload["ready_for_real_read_smoke"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
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
