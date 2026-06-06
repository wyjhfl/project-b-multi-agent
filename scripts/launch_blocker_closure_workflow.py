from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

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
    "只读上线阻断项关闭工作流",
    "仅消费 Launch Blocker Register 与可选脱敏关闭证据 JSON 的结构化字段",
    "不读取 Markdown 报告正文，不修改上游报告，不修改 .env 或环境变量",
    "不写业务数据、审计数据或指标数据",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码或 webhook 原文",
    "不执行真实外网 LLM，不连接真实外部 MCP、IdP、业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更",
    "不自动批准上线，不自动关闭 blocker，不创建 GitHub Release，不打 tag",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线，不宣称生产级 SSO/OIDC、多租户、真实 LLM、SRE/DR、容量或合规验收完成",
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


def _load_json_source(name: str, path_value: str | Path | None, *, required: bool) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "required": required,
            "status": "skipped",
            "payload": {},
            "missing_conditions": [f"{name}:input_not_provided"] if required else [],
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    sanitized_path = _sanitize_text(path)
    if not path.exists():
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "required": required,
            "status": "skipped",
            "payload": {},
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "required": required,
            "status": "skipped",
            "payload": {},
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "required": required,
            "status": "skipped",
            "payload": {},
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "required": required,
            "status": "skipped",
            "payload": {},
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    status = _normalize_status(payload.get("status") or payload.get("readiness_status"))
    secret_detected = _contains_secret_like_payload(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]

    if status == "skipped":
        missing_conditions.append(f"{name}:source_status_skipped")
    if status in {"blocked", "failed"}:
        missing_conditions.append(f"{name}:source_status_{status}")
    if payload.get("read_only") is False:
        missing_conditions.append(f"{name}:not_read_only")
    for flag in [
        "real_llm_executed",
        "external_mcp_connected",
        "external_system_connected",
        "deployment_executed",
        "migration_executed",
        "release_created",
        "tag_created",
        "rollback_executed",
        "security_scan_executed",
        "secret_rotation_executed",
        "auto_approved",
        "auto_closed",
    ]:
        if bool(payload.get(flag, False)):
            missing_conditions.append(f"{name}:{flag}_unexpected")
    if secret_detected:
        missing_conditions.append(f"{name}:secret_like_value_detected")
        warnings.append(f"{name}:secret_like_value_detected")

    return {
        "name": name,
        "path": sanitized_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "required": required,
        "status": status,
        "payload": payload,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "secret_detected": secret_detected,
    }


def _build_evidence_index(evidence_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_items = _safe_list(evidence_payload.get("closure_items") or evidence_payload.get("items"))
    index: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        candidates = [
            item.get("blocker_id"),
            item.get("source_key"),
            item.get("source_blocker_id"),
            item.get("id"),
        ]
        for candidate in candidates:
            if candidate:
                index[_sanitize_text(candidate)] = item
    return index


def _evidence_state(blocker: dict[str, Any], evidence: dict[str, Any] | None) -> tuple[str, list[str]]:
    source_status = str(blocker.get("status") or "open")
    source_key = _sanitize_text(blocker.get("source_key") or blocker.get("blocker_id") or "unknown")
    missing: list[str] = []

    if source_status == "blocked":
        return "blocked", [f"{source_key}:source_blocked"]
    if source_status == "skipped":
        return "skipped", [f"{source_key}:source_skipped"]
    if not evidence:
        return "evidence_missing", [f"{source_key}:closure_evidence_missing"]

    owner = _sanitize_text(evidence.get("owner") or "")
    due_at = _sanitize_text(evidence.get("due_at") or "")
    controls = [_sanitize_text(item) for item in _safe_list(evidence.get("compensating_controls"))]
    refs = [_sanitize_text(item) for item in _safe_list(evidence.get("closure_evidence_refs") or evidence.get("closure_evidence"))]
    reviewer = _sanitize_text(evidence.get("reviewer") or "")
    approval_state = _sanitize_text(evidence.get("approval_state") or "not_approved")

    if not owner or owner == "manual_owner_required":
        missing.append(f"{source_key}:owner_missing")
    if not due_at or due_at == "manual_due_date_required":
        missing.append(f"{source_key}:due_at_missing")
    if not controls or "manual_compensating_controls_required" in controls:
        missing.append(f"{source_key}:compensating_controls_missing")
    if not refs or "manual_closure_evidence_required" in refs:
        missing.append(f"{source_key}:closure_evidence_refs_missing")
    if not reviewer:
        missing.append(f"{source_key}:reviewer_missing")
    if approval_state not in {"approved", "pending_review"}:
        missing.append(f"{source_key}:approval_state_not_ready")

    if approval_state == "rejected":
        return "blocked", missing + [f"{source_key}:approval_rejected"]
    if missing:
        return "evidence_incomplete", missing
    return "review_ready", []


def _build_closure_items(blocker_payload: dict[str, Any], evidence_payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = _safe_list(blocker_payload.get("blocker_register"))
    evidence_index = _build_evidence_index(evidence_payload)
    rows = []
    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        blocker_id = _sanitize_text(blocker.get("blocker_id") or "unknown")
        source_key = _sanitize_text(blocker.get("source_key") or blocker_id)
        evidence = evidence_index.get(blocker_id) or evidence_index.get(source_key)
        state, missing = _evidence_state(blocker, evidence)
        rows.append(
            {
                "blocker_id": blocker_id,
                "source_key": source_key,
                "scope": _sanitize_text(blocker.get("scope") or "launch"),
                "source_status": _sanitize_text(blocker.get("status") or "open"),
                "closure_state": state,
                "owner": _sanitize_text((evidence or {}).get("owner") or blocker.get("owner") or "manual_owner_required"),
                "due_at": _sanitize_text((evidence or {}).get("due_at") or blocker.get("due_at") or "manual_due_date_required"),
                "approval_state": _sanitize_text((evidence or {}).get("approval_state") or "not_approved"),
                "manual_review_required": True,
                "auto_closed": False,
                "missing_conditions": missing,
            }
        )
    return rows


def _evidence_readiness_summary(evidence_payload: dict[str, Any]) -> dict[str, Any]:
    raw = (
        evidence_payload.get("evidence_readiness_summary")
        if isinstance(evidence_payload.get("evidence_readiness_summary"), dict)
        else {}
    )
    return {
        "local_evidence_available_count": int(raw.get("local_evidence_available_count", 0) or 0),
        "runbook_only_count": int(raw.get("runbook_only_count", 0) or 0),
        "missing_count": int(raw.get("missing_count", 0) or 0),
        "manual_review_required": bool(raw.get("manual_review_required", False)),
        "auto_approved": bool(raw.get("auto_approved", False)),
        "auto_closed": bool(raw.get("auto_closed", False)),
    }


def _derive_status(sources: list[dict[str, Any]], closure_items: list[dict[str, Any]]) -> str:
    required_source = sources[0]
    if any(source.get("secret_detected") for source in sources):
        return "blocked"
    if any(source.get("status") in {"blocked", "failed"} for source in sources):
        return "blocked"
    if any(
        any(marker in condition for marker in ["_unexpected", "not_read_only", "secret_like_value_detected"])
        for source in sources
        for condition in source.get("missing_conditions", [])
    ):
        return "blocked"
    if not required_source.get("loaded"):
        return "skipped"
    if not closure_items:
        return "skipped"
    states = {item.get("closure_state") for item in closure_items}
    if "blocked" in states:
        return "blocked"
    if states == {"skipped"}:
        return "skipped"
    if states == {"review_ready"}:
        return "partial"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.1 Launch Blocker Closure Workflow（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- closure_item_count: {payload.get('closure_item_count', 0)}",
        f"- review_ready_count: {payload.get('review_ready_count', 0)}",
        "",
        "## Closure Items",
    ]
    for item in payload.get("closure_items", []):
        lines.append(
            f"- {item.get('blocker_id')}: {item.get('closure_state')} | {item.get('scope')} | {item.get('source_key')}"
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


def build_launch_blocker_closure_workflow(
    *,
    output_dir: str | Path | None = None,
    launch_blockers: str | Path | None = None,
    closure_evidence: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    blocker_source = _load_json_source("launch_blockers", launch_blockers, required=True)
    evidence_source = _load_json_source("closure_evidence", closure_evidence, required=False)
    sources = [blocker_source, evidence_source]
    blocker_payload = blocker_source.get("payload", {}) if isinstance(blocker_source.get("payload"), dict) else {}
    evidence_payload = evidence_source.get("payload", {}) if isinstance(evidence_source.get("payload"), dict) else {}
    closure_items = _build_closure_items(blocker_payload, evidence_payload) if blocker_source.get("loaded") else []
    evidence_readiness_summary = _evidence_readiness_summary(evidence_payload)
    status = _derive_status(sources, closure_items)

    source_missing = [condition for source in sources for condition in source.get("missing_conditions", [])]
    item_missing = [condition for item in closure_items for condition in item.get("missing_conditions", [])]
    missing_conditions = sorted(set(source_missing + item_missing))
    warnings = sorted(set(warning for source in sources for warning in source.get("warnings", [])))
    review_ready_count = sum(1 for item in closure_items if item.get("closure_state") == "review_ready")
    incomplete_count = sum(1 for item in closure_items if item.get("closure_state") == "evidence_incomplete")
    missing_count = sum(1 for item in closure_items if item.get("closure_state") == "evidence_missing")
    blocked_count = sum(1 for item in closure_items if item.get("closure_state") == "blocked")
    skipped_count = sum(1 for item in closure_items if item.get("closure_state") == "skipped")

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.1.0-planning",
        "phase": "v4.1_phase_21.1",
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
        "audit_export_executed": False,
        "auto_approved": False,
        "auto_closed": False,
        "input_sources": [
            {
                "name": source.get("name"),
                "path": source.get("path"),
                "provided": source.get("provided"),
                "exists": source.get("exists"),
                "loaded": source.get("loaded"),
                "required": source.get("required"),
                "status": source.get("status"),
                "secret_detected": source.get("secret_detected"),
            }
            for source in sources
        ],
        "closure_items": closure_items,
        "closure_item_count": len(closure_items),
        "review_ready_count": review_ready_count,
        "evidence_incomplete_count": incomplete_count,
        "evidence_missing_count": missing_count,
        "evidence_readiness_summary": evidence_readiness_summary,
        "blocked_closure_count": blocked_count,
        "skipped_closure_count": skipped_count,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "关闭工作流仅判断证据是否可进入人工复核，不自动批准上线，也不自动关闭 blocker。",
        },
        "next_actions": [
            "为 evidence_missing 和 evidence_incomplete 项补齐 owner、due_at、补偿控制、证据引用、reviewer 与审批状态。",
            "review_ready 仅表示可进入人工复核，不表示已生产 Go。",
            "人工签核后重新生成 Launch Readiness、Blocker Register 与 Closure Workflow。",
            "最终生产 Go 需要独立变更审批与发布窗口确认。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_launch_blocker_closure_workflow"
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
        "closure_item_count": len(closure_items),
        "review_ready_count": review_ready_count,
        "evidence_missing_count": missing_count,
        "evidence_incomplete_count": incomplete_count,
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.1 上线阻断项关闭工作流只读报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--launch-blockers", default=None)
    parser.add_argument("--closure-evidence", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_launch_blocker_closure_workflow(
        output_dir=args.output_dir,
        launch_blockers=args.launch_blockers,
        closure_evidence=args.closure_evidence,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
