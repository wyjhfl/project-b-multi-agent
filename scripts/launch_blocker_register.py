from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "launch_blockers"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
BLOCKER_STATUS_VOCABULARY = ["open", "skipped", "blocked", "closed"]

CANONICAL_BLOCKERS = [
    "production_sso_oidc_signoff_missing",
    "tenant_isolation_production_acceptance_missing",
    "real_llm_production_acceptance_missing",
    "external_mcp_production_acceptance_missing",
    "business_system_integration_acceptance_missing",
    "postgres_redis_production_acceptance_missing",
    "sre_apm_alerting_oncall_acceptance_missing",
    "backup_restore_dr_failover_evidence_missing",
    "capacity_load_soak_test_evidence_missing",
    "external_security_scan_and_signoff_missing",
    "secret_rotation_leakage_response_drill_missing",
    "release_gate_change_approval_missing",
    "rollback_drill_and_freeze_window_missing",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

SECRET_FIELD_NAMES = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "jwt_secret",
    "password",
    "secret",
    "database_url",
    "redis_url",
    "webhook",
}

BOUNDARY_DECLARATIONS = [
    "只读生产上线阻断项登记册",
    "仅消费 Launch Readiness JSON 的结构化字段，不读取 Markdown 报告正文",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不修改上游报告",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
    "不连接真实外部 MCP、IdP、业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更",
    "不自动批准上线",
    "不自动关闭阻断项",
    "不创建 GitHub Release",
    "不打 tag，不移动、不删除、不重建历史 tag",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称生产级 SSO/OIDC、多租户、真实 LLM、SRE/DR、容量或合规验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_text(value: Any) -> bool:
    return any(pattern.search(str(value)) for pattern in SECRET_TEXT_PATTERNS)


def _contains_secret_like_payload(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key in SECRET_FIELD_NAMES and str(item).strip():
                return True
            if _contains_secret_like_payload(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret_like_payload(item) for item in value)
    return _contains_secret_like_text(value)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    return "partial" if raw else "skipped"


def _load_launch_readiness(path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["launch_readiness:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    sanitized_path = _sanitize_text(path)
    if not path.exists():
        return {
            "path": sanitized_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["launch_readiness:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["launch_readiness:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["launch_readiness:json_parse_failed"],
            "warnings": [f"launch_readiness:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["launch_readiness:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    status = _normalize_status(payload.get("status") or payload.get("readiness_status"))
    secret_detected = _contains_secret_like_payload(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]

    if status == "skipped":
        missing_conditions.append("launch_readiness:source_status_skipped")
    if status in {"blocked", "failed"}:
        missing_conditions.append(f"launch_readiness:source_status_{status}")
    if payload.get("read_only") is False:
        missing_conditions.append("launch_readiness:not_read_only")
    if bool(payload.get("real_llm_executed", False)):
        missing_conditions.append("launch_readiness:real_llm_executed_unexpected")
    if bool(payload.get("external_mcp_connected", False)):
        missing_conditions.append("launch_readiness:external_mcp_connected_unexpected")
    if bool(payload.get("external_system_connected", False)):
        missing_conditions.append("launch_readiness:external_system_connected_unexpected")
    if bool(payload.get("release_created", False)):
        missing_conditions.append("launch_readiness:release_created_unexpected")
    if bool(payload.get("tag_created", False)):
        missing_conditions.append("launch_readiness:tag_created_unexpected")
    if bool(payload.get("auto_approved", False)):
        missing_conditions.append("launch_readiness:auto_approved_unexpected")
    if bool(payload.get("auto_closed", False)):
        missing_conditions.append("launch_readiness:auto_closed_unexpected")
    if secret_detected:
        missing_conditions.append("launch_readiness:secret_like_value_detected")
        warnings.append("launch_readiness:secret_like_value_detected")

    return {
        "path": sanitized_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "payload": payload,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "secret_detected": secret_detected,
    }


def _scope_for_blocker(blocker_id: str) -> str:
    if "sso" in blocker_id or "tenant" in blocker_id:
        return "identity"
    if "llm" in blocker_id or "mcp" in blocker_id or "business_system" in blocker_id:
        return "integration"
    if "postgres" in blocker_id or "redis" in blocker_id:
        return "storage"
    if any(token in blocker_id for token in ["sre", "backup", "capacity"]):
        return "sre"
    if any(token in blocker_id for token in ["security", "secret"]):
        return "security"
    if any(token in blocker_id for token in ["release", "rollback"]):
        return "release"
    return "launch"


def _blocker_status(source_status: str, source_missing: list[str], blocker_id: str, input_loaded: bool) -> str:
    if any("secret_like_value_detected" in item for item in source_missing):
        return "blocked"
    if source_status in {"blocked", "failed"}:
        return "blocked"
    if any(
        marker in item
        for item in source_missing
        for marker in [
            "not_read_only",
            "real_llm_executed_unexpected",
            "external_mcp_connected_unexpected",
            "external_system_connected_unexpected",
            "release_created_unexpected",
            "tag_created_unexpected",
            "auto_approved_unexpected",
            "auto_closed_unexpected",
        ]
    ):
        return "blocked"
    if source_status == "skipped":
        return "skipped"
    if not input_loaded:
        return "skipped"
    if blocker_id in source_missing or blocker_id in CANONICAL_BLOCKERS:
        return "open"
    return "open"


def _build_register(source: dict[str, Any]) -> list[dict[str, Any]]:
    payload = source.get("payload", {}) if isinstance(source.get("payload"), dict) else {}
    source_blockers = [_sanitize_text(item) for item in _safe_list(payload.get("production_blockers"))]
    source_missing = [_sanitize_text(item) for item in source.get("missing_conditions", [])]
    blocker_ids = sorted(set(CANONICAL_BLOCKERS + source_blockers + [item for item in source_missing if ":" not in item]))

    register = []
    for index, blocker_id in enumerate(blocker_ids, start=1):
        scope = _scope_for_blocker(blocker_id)
        status = _blocker_status(str(source.get("status", "skipped")), source_missing, blocker_id, bool(source.get("loaded")))
        register.append(
            {
                "blocker_id": f"LB-{index:03d}",
                "source": "launch_readiness",
                "source_key": blocker_id,
                "risk_description": f"生产上线阻断项待关闭：{blocker_id}",
                "scope": scope,
                "owner": "manual_owner_required",
                "due_at": "manual_due_date_required",
                "compensating_controls": ["manual_compensating_controls_required"],
                "closure_evidence": ["manual_closure_evidence_required"],
                "status": status,
                "approval_state": "not_approved",
                "next_actions": [
                    "指定责任人和到期时间",
                    "补齐关闭证据和补偿控制",
                    "人工复核后再进入生产 Go/No-Go",
                ],
            }
        )
    return register


def _derive_status(source: dict[str, Any], register: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "blocked" for item in register):
        return "blocked"
    if not source.get("loaded"):
        return "skipped"
    if any(item.get("status") == "skipped" for item in register):
        return "skipped"
    if any(item.get("status") == "open" for item in register):
        return "partial"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.0 Launch Blocker Register（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- blocker_count: {payload.get('blocker_count', 0)}",
        f"- open_blocker_count: {payload.get('open_blocker_count', 0)}",
        "",
        "## Blockers",
    ]
    for item in payload.get("blocker_register", []):
        lines.append(
            f"- {item.get('blocker_id')}: {item.get('status')} | {item.get('scope')} | {item.get('source_key')}"
        )

    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_launch_blocker_register(
    *,
    output_dir: str | Path | None = None,
    launch_readiness: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    source = _load_launch_readiness(launch_readiness)
    register = _build_register(source)
    status = _derive_status(source, register)
    missing_conditions = sorted(set(_sanitize_text(item) for item in source.get("missing_conditions", [])))
    warnings = sorted(set(_sanitize_text(item) for item in source.get("warnings", [])))

    blocker_count = len(register)
    open_blocker_count = sum(1 for item in register if item.get("status") == "open")
    blocked_blocker_count = sum(1 for item in register if item.get("status") == "blocked")
    skipped_blocker_count = sum(1 for item in register if item.get("status") == "skipped")

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.0.0-planning",
        "phase": "v4.0_phase_20.2",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "online_endpoints_called": False,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "deployment_executed": False,
        "migration_executed": False,
        "release_created": False,
        "tag_created": False,
        "rollback_executed": False,
        "security_scan_executed": False,
        "secret_rotation_executed": False,
        "auto_approved": False,
        "auto_closed": False,
        "launch_readiness_source": {
            "path": source.get("path", ""),
            "provided": source.get("provided", False),
            "exists": source.get("exists", False),
            "loaded": source.get("loaded", False),
            "status": source.get("status", "skipped"),
            "secret_detected": source.get("secret_detected", False),
        },
        "blocker_register": register,
        "blocker_count": blocker_count,
        "open_blocker_count": open_blocker_count,
        "blocked_blocker_count": blocked_blocker_count,
        "skipped_blocker_count": skipped_blocker_count,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "所有 launch blocker 需要人工责任人、到期时间、补偿控制和关闭证据；脚本不自动批准上线。",
        },
        "next_actions": [
            "逐项补齐 owner、due_at、compensating_controls 和 closure_evidence。",
            "关闭 blocker 前保留上游 skipped/blocked/partial 语义。",
            "阻断项关闭后重新生成 Launch Readiness Review 与本登记册。",
            "最终生产 Go 需要人工签核，脚本不自动批准。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_launch_blocker_register"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "blocker_count": blocker_count,
        "open_blocker_count": open_blocker_count,
        "blocked_blocker_count": blocked_blocker_count,
        "skipped_blocker_count": skipped_blocker_count,
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.0 生产上线阻断项只读登记册（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--launch-readiness", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_launch_blocker_register(output_dir=args.output_dir, launch_readiness=args.launch_readiness)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
