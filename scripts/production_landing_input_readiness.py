from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_input_readiness"
DEFAULT_BUSINESS_ENV = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke" / "business_read_smoke.env.template"
DEFAULT_BUSINESS_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke"
DEFAULT_CLOSURE_EVIDENCE = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure" / "closure_evidence.template.json"
DEFAULT_MANUAL_SIGNOFF_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_package"
DEFAULT_MANUAL_SIGNOFF = DEFAULT_MANUAL_SIGNOFF_DIR / "manual_signoff_record.template.json"
DEFAULT_FILLED_MANUAL_SIGNOFF = DEFAULT_MANUAL_SIGNOFF_DIR / "manual_signoff_record.json"
DEFAULT_DRAFT_MANUAL_SIGNOFF = DEFAULT_MANUAL_SIGNOFF_DIR / "manual_signoff_record.draft.json"
DEFAULT_PILOT_SIGNOFF_DIR = ROOT_DIR / "docs" / "reports" / "production_pilot_signoff"
DEFAULT_LAUNCH_BLOCKER_DIR = ROOT_DIR / "docs" / "reports" / "launch_blockers"
DEFAULT_CLOSURE_INDEX_DIR = ROOT_DIR / "docs" / "reports" / "closure_evidence_index"

SAFE_REAL_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_llm_preflight.ps1"
SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains postgres -UseExistingEnv -EnvPath local\\production_landing.staging.env"
)
SAFE_REDIS_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains redis -UseExistingEnv -EnvPath local\\production_landing.staging.env"
)
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -UseExistingEnv -EnvPath local\\production_landing.staging.env -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)

REQUIRED_SIGNOFF_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")
REQUIRED_EVIDENCE_ACKS = (
    "real_llm_preflight",
    "postgres_redis_mcp_smoke",
    "business_read_smoke",
    "closure_evidence_review",
)
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip(" \"'<>[]{}\\")
                if candidate.lower() in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _read_json(path: Path, source_id: str) -> tuple[dict[str, Any], list[str], bool]:
    if not path.exists():
        return {}, [f"{source_id}:path_not_found"], False
    if not path.is_file() or path.suffix.lower() != ".json":
        return {}, [f"{source_id}:json_file_required"], False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, [f"{source_id}:json_parse_failed"], False
    if not isinstance(payload, dict):
        return {}, [f"{source_id}:json_object_required"], False
    return payload, [], _contains_secret_like(payload)


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None
    return max(files, key=_json_report_sort_key)


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _latest_or_placeholder(directory: Path, pattern: str, placeholder: str) -> str:
    latest = _latest_json(directory, pattern)
    return str(latest) if latest else placeholder


def _default_manual_signoff_path() -> Path:
    for path in (DEFAULT_FILLED_MANUAL_SIGNOFF, DEFAULT_DRAFT_MANUAL_SIGNOFF, DEFAULT_MANUAL_SIGNOFF):
        if path.exists():
            return path
    return DEFAULT_MANUAL_SIGNOFF


def _next_action_specs() -> dict[str, dict[str, Any]]:
    latest_launch_blockers = _latest_or_placeholder(
        DEFAULT_LAUNCH_BLOCKER_DIR,
        "*_launch_blocker_register.json",
        "docs/reports/launch_blockers/<latest-launch-blockers.json>",
    )
    latest_closure_index = _latest_or_placeholder(
        DEFAULT_CLOSURE_INDEX_DIR,
        "*_closure_evidence_index.json",
        "docs/reports/closure_evidence_index/<latest-closure-index.json>",
    )
    return {
        "business_system_read_only_credentials": {
            "next_action": "填写本地业务系统只读凭据后执行只读 smoke；不得提交真实 token。",
            "command_after_fill": SAFE_BUSINESS_READ_SMOKE_COMMAND,
            "required_env": [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
                "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>",
            ],
        },
        "launch_blocker_closure_evidence": {
            "next_action": "补齐 blocker owner/reviewer/due_at/证据引用后重新生成 closure workflow。",
            "command_after_fill": (
                "python scripts/launch_blocker_closure_workflow.py "
                f"--launch-blockers {latest_launch_blockers} --closure-evidence {DEFAULT_CLOSURE_EVIDENCE}"
            ),
        },
        "real_infra_current_round_acceptance": {
            "next_action": "在本地 secret 管理环境中启用 Postgres/Redis/MCP 同轮真实 smoke，并重新生成 signoff。",
            "command_after_fill": " ; ".join(
                [
                    SAFE_REAL_LLM_PREFLIGHT_COMMAND,
                    SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
                    SAFE_REDIS_INFRA_SMOKE_COMMAND,
                    SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
                ]
            ),
            "required_env": [
                "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
                "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
                "REAL_LLM_ACCEPTANCE_ENABLED=true",
                "REAL_LLM_PREFLIGHT_ENABLED=true",
                "REAL_LLM_SMOKE_ENABLED=true",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
                "REAL_LLM_PROVIDER=litellm",
                "REAL_LLM_MODEL=gpt-5.5",
                "REAL_LLM_BASE_URL=http://100.119.206.22:8300/v1",
                "REAL_LLM_API_KEY_ENV=REAL_LLM_API_KEY",
                "REAL_LLM_API_KEY=<secret-managed-token>",
                "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                "REDIS_STAGING_SMOKE_EXECUTE=true",
                "MCP_STAGING_SMOKE_EXECUTE=true",
                "STORAGE_BACKEND=postgres",
                "DATABASE_URL=<secret-managed-url>",
                "REDIS_ENABLED=true",
                "REDIS_URL=<secret-managed-url>",
                "RATE_LIMIT_BACKEND=redis",
                "MCP_MODE=real",
                "MCP_SERVER_COMMAND=<approved-command>",
                "MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>",
                "MCP_TOOL_ALLOWLIST=<approved-tools>",
            ],
        },
        "manual_signoff_record": {
            "next_action": "由 release/security/business/operations 四类负责人完成人工签核，保持 public_production_direct_launch=No-Go。",
            "command_after_fill": (
                "python scripts/manual_signoff_package.py "
                f"--closure-index {latest_closure_index} --signoff-record {DEFAULT_MANUAL_SIGNOFF}"
            ),
        },
    }

def _attach_next_actions(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = _next_action_specs()
    enriched: list[dict[str, Any]] = []
    for item in inputs:
        row = dict(item)
        spec = specs.get(str(row.get("input_id") or ""), {})
        if row.get("status") != "ready" and spec:
            row.update(spec)
        enriched.append(row)
    return enriched


def _parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    if not path.exists():
        return {}, ["business_env:path_not_found"]
    if not path.is_file():
        return {}, ["business_env:file_required"]
    values: dict[str, str] = {}
    warnings: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            warnings.append("business_env:malformed_line")
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values, warnings


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped.startswith("<") or stripped.endswith("_required") or "manual_" in stripped


def _check_business_env(path: Path) -> dict[str, Any]:
    values, warnings = _parse_env_file(path)
    missing: list[str] = list(warnings)
    required_equals = {
        "BUSINESS_INTEGRATION_ENABLED": "true",
        "BUSINESS_INTEGRATION_READ_ONLY": "true",
        "BUSINESS_INTEGRATION_WRITE_ENABLED": "false",
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED": "true",
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED": "true",
    }
    for key, expected in required_equals.items():
        if values.get(key, "").lower() != expected:
            missing.append(f"business_env:{key}_must_be_{expected}")
    if "business_read_probe" not in values.get("BUSINESS_SYSTEM_TOOL_ALLOWLIST", ""):
        missing.append("business_env:BUSINESS_SYSTEM_TOOL_ALLOWLIST_missing_business_read_probe")
    if values.get("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "").strip():
        missing.append("business_env:BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST_must_be_empty")
    for key in ("BUSINESS_SYSTEM_NAME", "BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_TOKEN_ENV"):
        if _is_placeholder(values.get(key, "")):
            missing.append(f"business_env:{key}_not_filled")
    if _is_placeholder(values.get("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "")):
        missing.append("business_env:BUSINESS_SYSTEM_AUTH_HEADER_NAME_not_filled")
    for key in (
        "BUSINESS_SYSTEM_BUSINESS_OWNER",
        "BUSINESS_SYSTEM_SECURITY_REVIEWER",
        "BUSINESS_SYSTEM_OPERATIONS_OWNER",
        "BUSINESS_SYSTEM_DATA_OWNER",
    ):
        if _is_placeholder(values.get(key, "")):
            missing.append(f"business_env:{key}_not_filled")
    base_url = values.get("BUSINESS_SYSTEM_BASE_URL", "")
    token = values.get("BUSINESS_SYSTEM_TOKEN", "")
    if _is_placeholder(base_url):
        missing.append("business_env:BUSINESS_SYSTEM_BASE_URL_not_filled")
    if _is_placeholder(token):
        missing.append("business_env:BUSINESS_SYSTEM_TOKEN_not_filled")
    if values and values.get("BUSINESS_INTEGRATION_WRITE_ENABLED", "").lower() == "true":
        missing.append("business_env:write_enabled_unexpected")
    return {
        "input_id": "business_system_read_only_credentials",
        "path": str(path),
        "present": path.exists(),
        "status": "ready" if not missing else "partial",
        "missing_conditions": sorted(set(missing)),
        "base_url_present": bool(base_url and not _is_placeholder(base_url)),
        "token_present": bool(token and not _is_placeholder(token)),
        "read_only": values.get("BUSINESS_INTEGRATION_READ_ONLY", "").lower() == "true",
        "write_enabled": values.get("BUSINESS_INTEGRATION_WRITE_ENABLED", "").lower() == "true",
        "secret_plaintext_output": False,
    }


def _check_business_smoke(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload, missing, secret_detected = _read_json(path, "business_system_read_smoke")
    if missing:
        return None
    smoke_missing: list[str] = []
    if payload.get("status") != "success":
        smoke_missing.append("business_smoke:not_success")
    if payload.get("business_system_connected") is not True:
        smoke_missing.append("business_smoke:business_system_connected_not_true")
    if payload.get("business_read_executed") is not True:
        smoke_missing.append("business_smoke:business_read_executed_not_true")
    if payload.get("business_write_executed") is True or payload.get("business_data_written") is True:
        smoke_missing.append("business_smoke:write_or_data_written_unexpected")
    if payload.get("local_business_mock_used") is True:
        smoke_missing.append("business_smoke:local_business_mock_not_valid_for_real_production")
    if payload.get("approval_bypassed") is True or payload.get("audit_bypassed") is True:
        smoke_missing.append("business_smoke:approval_or_audit_bypassed")
    if secret_detected:
        smoke_missing.append("business_smoke:secret_like_value_detected")
    status = "blocked" if secret_detected else ("ready" if not smoke_missing else "partial")
    return {
        "input_id": "business_system_read_only_credentials",
        "path": str(path),
        "present": path.exists(),
        "status": status,
        "evidence_source": "business_system_read_smoke",
        "missing_conditions": sorted(set(smoke_missing)),
        "business_system_connected": payload.get("business_system_connected") is True,
        "business_read_executed": payload.get("business_read_executed") is True,
        "business_write_executed": payload.get("business_write_executed") is True,
        "business_data_written": payload.get("business_data_written") is True,
        "local_business_mock_used": payload.get("local_business_mock_used") is True,
        "read_only": payload.get("read_only") is True,
        "write_enabled": False,
        "secret_plaintext_output": False,
    }


def _check_closure_evidence(path: Path) -> dict[str, Any]:
    payload, missing, secret_detected = _read_json(path, "closure_evidence")
    items = payload.get("closure_items") if isinstance(payload.get("closure_items"), list) else []
    ready_count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            missing.append(f"closure_evidence:item_{index}_not_object")
            continue
        item_id = str(item.get("blocker_id") or f"item_{index}")
        if _is_placeholder(str(item.get("owner") or "")):
            missing.append(f"closure_evidence:{item_id}:owner_not_filled")
        if _is_placeholder(str(item.get("due_at") or "")):
            missing.append(f"closure_evidence:{item_id}:due_at_not_filled")
        controls = item.get("compensating_controls") if isinstance(item.get("compensating_controls"), list) else []
        refs = item.get("closure_evidence_refs") if isinstance(item.get("closure_evidence_refs"), list) else []
        if not controls or any(_is_placeholder(str(value)) for value in controls):
            missing.append(f"closure_evidence:{item_id}:compensating_controls_not_filled")
        if not refs or any(_is_placeholder(str(value)) for value in refs):
            missing.append(f"closure_evidence:{item_id}:closure_evidence_refs_not_filled")
        if _is_placeholder(str(item.get("reviewer") or "")):
            missing.append(f"closure_evidence:{item_id}:reviewer_not_filled")
        approval_state = str(item.get("approval_state") or "")
        if approval_state not in {"pending_review", "approved"}:
            missing.append(f"closure_evidence:{item_id}:approval_state_not_ready")
        else:
            ready_count += 1
    if not items:
        missing.append("closure_evidence:closure_items_missing")
    if payload.get("auto_approved") is True or payload.get("auto_closed") is True:
        missing.append("closure_evidence:auto_flag_unexpected")
    if secret_detected:
        missing.append("closure_evidence:secret_like_value_detected")
    status = "blocked" if secret_detected else ("ready" if not missing else "partial")
    return {
        "input_id": "launch_blocker_closure_evidence",
        "path": str(path),
        "present": path.exists(),
        "status": status,
        "closure_item_count": len(items),
        "ready_count": ready_count,
        "missing_conditions": sorted(set(missing)),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }


def _check_manual_signoff(path: Path) -> dict[str, Any]:
    payload, missing, secret_detected = _read_json(path, "manual_signoff_record")
    roles = payload.get("roles") if isinstance(payload.get("roles"), list) else []
    acknowledgements = (
        payload.get("evidence_acknowledgements")
        if isinstance(payload.get("evidence_acknowledgements"), list)
        else []
    )
    approved_roles = {
        str(item.get("role") or "")
        for item in roles
        if isinstance(item, dict) and item.get("approved") is True and str(item.get("name") or "").strip()
    }
    accepted_ack_ids = {
        str(item.get("item") or "").strip()
        for item in acknowledgements
        if isinstance(item, dict) and item.get("accepted") is True
    }
    if payload.get("manual_signoff_completed") is not True:
        missing.append("manual_signoff_record:not_completed")
    if str(payload.get("decision") or "").lower() != "go":
        missing.append("manual_signoff_record:decision_not_go")
    if str(payload.get("public_production_direct_launch") or "") != "No-Go":
        missing.append("manual_signoff_record:public_production_direct_launch_must_remain_no_go")
    for role in REQUIRED_SIGNOFF_ROLES:
        if role not in approved_roles:
            missing.append(f"manual_signoff_record:{role}_not_approved")
    for ack_id in REQUIRED_EVIDENCE_ACKS:
        if ack_id not in accepted_ack_ids:
            missing.append(f"manual_signoff_record:evidence_ack_{ack_id}_not_accepted")
    if payload.get("auto_signed") is True or payload.get("auto_approved") is True:
        missing.append("manual_signoff_record:auto_flag_unexpected")
    if secret_detected:
        missing.append("manual_signoff_record:secret_like_value_detected")
    status = "blocked" if secret_detected else ("ready" if not missing else "partial")
    return {
        "input_id": "manual_signoff_record",
        "path": str(path),
        "present": path.exists(),
        "status": status,
        "approved_roles": sorted(approved_roles),
        "missing_conditions": sorted(set(missing)),
        "secret_plaintext_output": False,
        "auto_approved": False,
    }


def _check_real_infra_current_round(signoff_report: Path | None) -> dict[str, Any]:
    missing: list[str] = []
    if signoff_report is None:
        missing.append("real_infra:production_pilot_signoff_report_not_found")
        payload: dict[str, Any] = {}
        secret_detected = False
    else:
        payload, read_missing, secret_detected = _read_json(signoff_report, "production_pilot_signoff")
        missing.extend(read_missing)

    landing = payload.get("landing_status") if isinstance(payload.get("landing_status"), dict) else {}
    production_blockers = landing.get("production_blockers") if isinstance(landing.get("production_blockers"), list) else []
    if landing.get("real_infra_ready") is not True:
        missing.append("real_infra:postgres_redis_mcp_not_all_connected")
    for flag in ("database_connected", "redis_connected", "external_mcp_connected"):
        if landing.get(flag) is not True:
            missing.append(f"real_infra:{flag}_not_true")
    if secret_detected:
        missing.append("real_infra:secret_like_value_detected")
    status = "blocked" if secret_detected else ("ready" if not missing else "partial")
    return {
        "input_id": "real_infra_current_round_acceptance",
        "path": str(signoff_report or DEFAULT_PILOT_SIGNOFF_DIR),
        "present": bool(signoff_report and signoff_report.exists()),
        "status": status,
        "database_connected": landing.get("database_connected") is True,
        "redis_connected": landing.get("redis_connected") is True,
        "external_mcp_connected": landing.get("external_mcp_connected") is True,
        "real_infra_ready": landing.get("real_infra_ready") is True,
        "production_blockers": [str(item) for item in production_blockers if str(item).startswith("real_infra:")],
        "missing_conditions": sorted(set(missing)),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地输入就绪检查（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_input_count: {payload.get('ready_input_count', 0)}",
        f"- missing_input_count: {payload.get('missing_input_count', 0)}",
        f"- blocked_input_count: {payload.get('blocked_input_count', 0)}",
        f"- required_input_count: {payload.get('required_input_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', '')}",
        "",
        "## Source Reports",
    ]
    for key, value in payload.get("source_reports", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Inputs",
        ]
    )
    for item in payload.get("inputs", []):
        lines.append(f"- {item.get('input_id')}: {item.get('status')} | missing={len(item.get('missing_conditions', []))}")
        if item.get("next_action"):
            lines.append(f"  - next_action: {item.get('next_action')}")
        if item.get("command_after_fill"):
            lines.append(f"  - command_after_fill: `{item.get('command_after_fill')}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "- 只读检查输入文件结构和占位状态，不连接真实业务系统。",
            "- 不输出 URL、token、API key、连接串或签核敏感细节原文。",
            "- 不自动批准上线，不自动关闭 blocker，public_production_direct_launch 始终保持 No-Go。",
            "",
        ]
    )
    return "\n".join(lines)


def build_production_landing_input_readiness(
    *,
    output_dir: str | Path | None = None,
    business_env: str | Path | None = None,
    closure_evidence: str | Path | None = None,
    manual_signoff: str | Path | None = None,
    pilot_signoff: str | Path | None = None,
    business_smoke: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    pilot_signoff_path = Path(pilot_signoff) if pilot_signoff else _latest_json(DEFAULT_PILOT_SIGNOFF_DIR, "*_production_pilot_signoff.json")
    business_smoke_path = (
        Path(business_smoke)
        if business_smoke
        else (_latest_json(DEFAULT_BUSINESS_SMOKE_DIR, "*_business_system_read_smoke.json") if business_env is None else None)
    )
    business_input = _check_business_smoke(business_smoke_path)
    if business_input is None:
        business_input = _check_business_env(Path(business_env) if business_env else DEFAULT_BUSINESS_ENV)
    inputs = _attach_next_actions([
        business_input,
        _check_closure_evidence(Path(closure_evidence) if closure_evidence else DEFAULT_CLOSURE_EVIDENCE),
        _check_real_infra_current_round(pilot_signoff_path),
        _check_manual_signoff(Path(manual_signoff) if manual_signoff else _default_manual_signoff_path()),
    ])
    ready_count = sum(1 for item in inputs if item.get("status") == "ready")
    blocked_count = sum(1 for item in inputs if item.get("status") == "blocked")
    missing_count = len(inputs) - ready_count
    status = "blocked" if blocked_count else ("success" if ready_count == len(inputs) else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    source_reports = {
        "business_env": str(Path(business_env) if business_env else DEFAULT_BUSINESS_ENV),
        "business_smoke": str(business_smoke_path or DEFAULT_BUSINESS_SMOKE_DIR),
        "closure_evidence": str(Path(closure_evidence) if closure_evidence else DEFAULT_CLOSURE_EVIDENCE),
        "pilot_signoff": str(pilot_signoff_path or DEFAULT_PILOT_SIGNOFF_DIR),
        "manual_signoff": str(Path(manual_signoff) if manual_signoff else _default_manual_signoff_path()),
    }
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.8",
        "phase": "v4.5 Phase 25.10 Production Landing Input Readiness",
        "status": status,
        "read_only": True,
        "source_reports": source_reports,
        "resolved_paths": source_reports,
        "inputs": inputs,
        "ready_input_count": ready_count,
        "required_input_count": len(inputs),
        "missing_input_count": missing_count,
        "blocked_input_count": blocked_count,
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "business_system_connected": False,
        "business_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_input_readiness"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "ready_input_count": ready_count,
        "required_input_count": len(inputs),
        "missing_input_count": missing_count,
        "blocked_input_count": blocked_count,
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地输入就绪只读检查报告。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--business-env", default=str(DEFAULT_BUSINESS_ENV))
    parser.add_argument("--closure-evidence", default=str(DEFAULT_CLOSURE_EVIDENCE))
    parser.add_argument("--manual-signoff", default=None)
    parser.add_argument("--pilot-signoff", default=None)
    parser.add_argument("--business-smoke", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_input_readiness(
        output_dir=args.output_dir,
        business_env=args.business_env,
        closure_evidence=args.closure_evidence,
        manual_signoff=args.manual_signoff,
        pilot_signoff=args.pilot_signoff,
        business_smoke=args.business_smoke,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

