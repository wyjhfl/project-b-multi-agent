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

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_production_readiness"
BUSINESS_SMOKE_REPORT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke"
STATUS_VOCABULARY = ["ready", "needs_input", "blocked", "failed"]
ENV_PATH_SAFE_KEYS = {
    "BUSINESS_INTEGRATION_ENABLED",
    "BUSINESS_INTEGRATION_READ_ONLY",
    "BUSINESS_INTEGRATION_WRITE_ENABLED",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
    "BUSINESS_SYSTEM_NAME",
    "BUSINESS_SYSTEM_BASE_URL_ENV",
    "BUSINESS_SYSTEM_TOKEN_ENV",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
    "BUSINESS_SYSTEM_READ_PROBE_PATH",
    "BUSINESS_SYSTEM_AUTH_HEADER_NAME",
    "BUSINESS_SYSTEM_AUTH_SCHEME",
    "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "BUSINESS_SYSTEM_DATA_OWNER",
}
ENV_PATH_SECRET_KEYS = {
    "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
    "XIAOMI_LLM_API_KEY",
    "JWT_SECRET",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _latest_json(directory: Path, pattern: str = "*.json") -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return (generated_at, item.stat().st_mtime, item.name)

    return max(files, key=sort_key)


def _resolve_env_path(env_path: str | Path | None) -> Path | None:
    if env_path is None or str(env_path).strip() == "":
        return None
    path = Path(env_path)
    return path if path.is_absolute() else ROOT_DIR / path


def _parse_env_path(env_path: str | Path | None) -> dict[str, Any]:
    resolved = _resolve_env_path(env_path)
    if resolved is None:
        return {
            "path": "",
            "present": False,
            "safe_values": {},
            "loaded_keys": [],
            "secret_keys_skipped": [],
            "unknown_keys_ignored": [],
        }
    if not resolved.exists():
        return {
            "path": str(resolved),
            "present": False,
            "safe_values": {},
            "loaded_keys": [],
            "secret_keys_skipped": [],
            "unknown_keys_ignored": [],
        }
    safe_values: dict[str, str] = {}
    secret_keys_skipped: list[str] = []
    unknown_keys_ignored: list[str] = []
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in ENV_PATH_SECRET_KEYS:
            secret_keys_skipped.append(key)
        elif key in ENV_PATH_SAFE_KEYS:
            safe_values[key] = value
        else:
            unknown_keys_ignored.append(key)
    return {
        "path": str(resolved),
        "present": True,
        "safe_values": safe_values,
        "loaded_keys": sorted(safe_values.keys()),
        "secret_keys_skipped": sorted(set(secret_keys_skipped)),
        "unknown_keys_ignored": sorted(set(unknown_keys_ignored)),
    }


def _apply_safe_env_values(env_values: dict[str, str]) -> dict[str, str | None]:
    previous = {key: os.environ.get(key) for key in env_values}
    for key, value in env_values.items():
        os.environ[key] = value
    return previous


def _restore_env_values(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _resolve_report_path(report_dir: Path, explicit_json_path: str | Path | None, expected_suffix: str) -> tuple[Path | None, bool, list[str]]:
    if explicit_json_path is None:
        return _latest_json(report_dir, f"*{expected_suffix}"), False, []

    candidate = Path(explicit_json_path)
    if not candidate.is_absolute():
        candidate = ROOT_DIR / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        return None, False, ["business_system_read_smoke:explicit_json_path_missing"]
    except OSError:
        return None, False, ["business_system_read_smoke:explicit_json_path_unresolvable"]

    expected_root = report_dir.resolve()
    if resolved.suffix.lower() != ".json":
        return None, False, ["business_system_read_smoke:explicit_json_path_not_json"]
    if not resolved.name.endswith(expected_suffix):
        return None, False, ["business_system_read_smoke:explicit_json_path_report_type_mismatch"]
    if expected_root != resolved and expected_root not in resolved.parents:
        return None, False, ["business_system_read_smoke:explicit_json_path_outside_report_dir"]
    return resolved, True, []


def _read_latest_business_smoke(
    report_dir: Path,
    explicit_json_path: str | Path | None = None,
) -> dict[str, Any]:
    latest, source_bound, source_issues = _resolve_report_path(
        report_dir,
        explicit_json_path,
        "_business_system_read_smoke.json",
    )
    if latest is None:
        return {
            "latest_report_present": False,
            "latest_json_path": str(explicit_json_path or ""),
            "status": "blocked" if source_issues else "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": False,
            "secret_plaintext_output": False,
            "source_bound": source_bound,
            "source_selection": "explicit_json_path" if explicit_json_path is not None else "latest_report_lookup",
            "missing_conditions": source_issues or ["business_system_read_smoke:report_not_found"],
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "failed",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": False,
            "secret_plaintext_output": False,
            "source_bound": source_bound,
            "source_selection": "explicit_json_path" if explicit_json_path is not None else "latest_report_lookup",
            "missing_conditions": ["business_system_read_smoke:json_parse_failed"],
        }
    secret_detected = _contains_secret_like(payload)
    return {
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "business_system_connected": bool(payload.get("business_system_connected", False)),
        "business_read_executed": bool(payload.get("business_read_executed", False)),
        "business_write_executed": bool(payload.get("business_write_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "local_business_mock_used": bool(payload.get("local_business_mock_used", False)),
        "demo_business_system_used": bool(payload.get("demo_business_system_used", False)),
        "secret_plaintext_output": secret_detected or bool(payload.get("secret_plaintext_output", False)),
        "source_bound": source_bound,
        "source_selection": "explicit_json_path" if explicit_json_path is not None else "latest_report_lookup",
        "missing_conditions": [
            str(item)
            for item in (
                payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
            )
        ]
        + (["business_system_read_smoke:secret_like_text_detected"] if secret_detected else []),
    }


def _owner_inputs() -> dict[str, bool]:
    keys = {
        "business_owner": "BUSINESS_SYSTEM_BUSINESS_OWNER",
        "security_reviewer": "BUSINESS_SYSTEM_SECURITY_REVIEWER",
        "operations_owner": "BUSINESS_SYSTEM_OPERATIONS_OWNER",
        "data_owner": "BUSINESS_SYSTEM_DATA_OWNER",
    }
    return {name: bool((os.getenv(env_key, "") or "").strip()) for name, env_key in keys.items()}


def _missing_conditions(smoke: dict[str, Any]) -> list[str]:
    config = load_business_system_config()
    owners = _owner_inputs()
    missing: list[str] = []

    for owner_name, present in owners.items():
        if not present:
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
        missing.append("env_target:BUSINESS_SYSTEM_BASE_URL_ENV_missing")
    if not config.token_env:
        missing.append("env:BUSINESS_SYSTEM_TOKEN_ENV_missing")
    elif not config.token_present:
        missing.append("env_target:BUSINESS_SYSTEM_TOKEN_ENV_missing")
    if not config.read_probe_path:
        missing.append("env:BUSINESS_SYSTEM_READ_PROBE_PATH_missing")
    if not config.auth_header_name:
        missing.append("env:BUSINESS_SYSTEM_AUTH_HEADER_NAME_missing")

    if smoke.get("business_read_executed") is not True:
        missing.append("evidence:business_system_real_read_smoke_not_executed")
    if smoke.get("local_business_mock_used") is True:
        missing.append("evidence:local_business_mock_not_valid_for_real_production")
    if smoke.get("demo_business_system_used") is True:
        missing.append("evidence:demo_business_system_not_valid_for_real_production")
    if smoke.get("business_write_executed") is True or smoke.get("business_data_written") is True:
        missing.append("boundary:business_write_detected")
    if smoke.get("secret_plaintext_output") is True:
        missing.append("boundary:secret_plaintext_output_detected")
        missing.append("boundary:secret_like_text_detected")
    return sorted(set(missing))


def _required_inputs() -> list[dict[str, str]]:
    return [
        {
            "id": "business_owners",
            "description": "提供业务、数据、安全、运维四类负责人标识。",
            "env": "BUSINESS_SYSTEM_BUSINESS_OWNER / BUSINESS_SYSTEM_DATA_OWNER / BUSINESS_SYSTEM_SECURITY_REVIEWER / BUSINESS_SYSTEM_OPERATIONS_OWNER",
        },
        {
            "id": "read_only_endpoint",
            "description": "提供只读健康或探测端点，必须可用最小权限 token 访问。",
            "env": "BUSINESS_SYSTEM_BASE_URL_ENV / BUSINESS_SYSTEM_BASE_URL / BUSINESS_SYSTEM_READ_PROBE_PATH",
        },
        {
            "id": "read_only_secret",
            "description": "通过当前进程或外部 secret manager 注入只读 token，不写入仓库或报告。",
            "env": "BUSINESS_SYSTEM_TOKEN_ENV / BUSINESS_SYSTEM_TOKEN",
        },
        {
            "id": "safe_execution",
            "description": "执行安全 PowerShell 入口生成脱敏 smoke 证据。",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
        },
    ]


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    lowered = text.lower()
    if "sk-" in lowered or "bearer " in lowered:
        return True
    safe_values = {
        "<secret-managed-token>",
        "<secret-managed-url>",
        "<set-in-local-env-only>",
        "<owner-or-staff-id>",
        "secret-managed-token",
        "secret-managed-url",
        "set-in-local-env-only",
    }
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
            normalized = raw_value.strip().strip("<>").lower()
            if normalized and normalized not in safe_values:
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
        "# 业务系统生产只读接入 Readiness Brief",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- missing_condition_count: {payload.get('missing_condition_count', 0)}",
        f"- business_read_executed: {payload.get('latest_business_smoke', {}).get('business_read_executed', False)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 下一步",
    ]
    for item in payload.get("next_actions", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 边界",
            "- 本 brief 只读取环境变量存在性和脱敏报告字段，不连接真实业务系统。",
            "- 真实业务 smoke 必须使用只读 token，且业务写入保持 false。",
            "- 本 brief 不代表公网生产直上，public_production_direct_launch 必须保持 No-Go。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_business_system_production_readiness"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def build_business_system_production_readiness_brief(
    *,
    output_dir: str | Path | None = None,
    business_smoke_report_dir: str | Path | None = None,
    business_smoke_json_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    smoke_dir = Path(business_smoke_report_dir) if business_smoke_report_dir else BUSINESS_SMOKE_REPORT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    env_path_summary = _parse_env_path(env_path)
    previous_env = _apply_safe_env_values(env_path_summary["safe_values"])
    try:
        config = load_business_system_config()
        latest_smoke = _read_latest_business_smoke(smoke_dir, explicit_json_path=business_smoke_json_path)
        missing = _missing_conditions(latest_smoke)
        owner_inputs_present = _owner_inputs()
    finally:
        _restore_env_values(previous_env)
    blocked_markers = [item for item in missing if item.startswith("boundary:")]
    status = "blocked" if blocked_markers else ("ready" if not missing else "needs_input")
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.4",
        "phase": "v4.5 Phase 25.6 Business System Production Readiness Brief",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "env_path": env_path_summary["path"],
        "env_file_present": env_path_summary["present"],
        "env_path_loaded_keys": env_path_summary["loaded_keys"],
        "env_path_loaded_key_count": len(env_path_summary["loaded_keys"]),
        "env_path_secret_keys_skipped": env_path_summary["secret_keys_skipped"],
        "env_path_secret_key_skipped_count": len(env_path_summary["secret_keys_skipped"]),
        "env_path_unknown_keys_ignored": env_path_summary["unknown_keys_ignored"],
        "env_path_unknown_key_ignored_count": len(env_path_summary["unknown_keys_ignored"]),
        "config": safe_config_summary(config),
        "owner_inputs_present": owner_inputs_present,
        "required_inputs": _required_inputs(),
        "source_bound": bool(latest_smoke.get("source_bound", False)),
        "latest_business_smoke": latest_smoke,
        "missing_conditions": missing,
        "missing_condition_count": len(missing),
        "next_actions": [
            "补齐 owner 环境变量和真实只读 URL/token 的外部注入。",
            "运行 scripts\\business_system_read_smoke.ps1 生成真实只读 smoke 证据。",
            "重新生成本 brief、controlled pilot operator packet 和最终 verification。",
        ],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": bool(latest_smoke.get("secret_plaintext_output", False)),
        "public_production_direct_launch": "No-Go",
        "output_dir": str(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["boundary:secret_like_text_detected"]))
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload = _redact_secret_like(payload)
    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "missing_condition_count": payload["missing_condition_count"],
        "business_read_executed": latest_smoke["business_read_executed"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
        "public_production_direct_launch": "No-Go",
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成业务系统生产只读接入 readiness brief。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--business-smoke-report-dir", default=str(BUSINESS_SMOKE_REPORT_DIR))
    parser.add_argument("--business-smoke-json-path", default=None)
    parser.add_argument("--env-path", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_business_system_production_readiness_brief(
        output_dir=args.output_dir,
        business_smoke_report_dir=args.business_smoke_report_dir,
        business_smoke_json_path=args.business_smoke_json_path,
        env_path=args.env_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready", "needs_input", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
