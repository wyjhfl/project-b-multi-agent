from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_package"
DEFAULT_CLOSURE_INDEX_DIR = ROOT_DIR / "docs" / "reports" / "closure_evidence_index"
DEFAULT_SIGNOFF_RECORD = DEFAULT_OUTPUT_DIR / "manual_signoff_record.template.json"
DEFAULT_FILLED_SIGNOFF_RECORD = DEFAULT_OUTPUT_DIR / "manual_signoff_record.json"
DEFAULT_DRAFT_SIGNOFF_RECORD = DEFAULT_OUTPUT_DIR / "manual_signoff_record.draft.json"
DEFAULT_REAL_LLM_PREFLIGHT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_real_llm_preflight"
DEFAULT_XIAOMI_PREFLIGHT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight"
DEFAULT_STAGING_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke"
DEFAULT_BUSINESS_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke"
DEFAULT_CLOSURE_WORKFLOW_DIR = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure"

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bk-[A-Za-z0-9_\-]{24,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

REQUIRED_SIGNOFF_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")
REQUIRED_EVIDENCE_ACKS = (
    "real_llm_preflight",
    "postgres_redis_mcp_smoke",
    "business_read_smoke",
    "closure_evidence_review",
)

BOUNDARY_DECLARATIONS = [
    "只读人工签核包。",
    "仅消费 closure evidence index JSON 和可选人工签核记录 JSON 的结构化字段。",
    "不读取 Markdown 报告正文。",
    "不读取或输出真实 secret 原文。",
    "不自动签核，不自动批准上线，不自动关闭 blocker。",
    "不修改、不移动、不删除输入证据。",
    "不执行真实外网 LLM，不连接真实外部系统。",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、安全扫描、审计导出、密钥轮换或权限变更。",
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


def _contains_secret_like_payload(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _latest_json(directory: Path, pattern: str) -> Path | None:
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


def _latest_evidence_path(directory: Path, pattern: str) -> str:
    latest = _latest_json(directory, pattern)
    return _sanitize_text(latest) if latest else ""


def _latest_real_llm_evidence_path() -> str:
    latest = _latest_evidence_path(
        DEFAULT_REAL_LLM_PREFLIGHT_DIR,
        "*_production_landing_real_llm_preflight.json",
    )
    if latest:
        return latest
    return _latest_evidence_path(
        DEFAULT_XIAOMI_PREFLIGHT_DIR,
        "*_production_landing_xiaomi_llm_preflight.json",
    )


def _resolve_cli_default_inputs(
    *,
    closure_index: str | Path | None,
    signoff_record: str | Path | None,
    output_dir: str | Path | None = None,
) -> tuple[str | Path | None, str | Path | None]:
    resolved_index = closure_index or _latest_json(DEFAULT_CLOSURE_INDEX_DIR, "*_closure_evidence_index.json")
    resolved_record = signoff_record or _default_signoff_record_path(output_dir)
    return resolved_index, resolved_record


def _default_signoff_record_path(output_dir: str | Path | None = None) -> Path | None:
    base_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    for path in (
        base_dir / "manual_signoff_record.json",
        base_dir / "manual_signoff_record.draft.json",
        base_dir / "manual_signoff_record.template.json",
    ):
        if path.exists():
            return path
    return None


def _load_json_object(path_value: str | Path | None, prefix: str) -> dict[str, Any]:
    if not path_value:
        return {
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "payload": {},
            "missing_conditions": [f"{prefix}:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }
    path = Path(path_value)
    safe_path = _sanitize_text(path)
    if not path.exists():
        return {
            "path": safe_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "payload": {},
            "missing_conditions": [f"{prefix}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "payload": {},
            "missing_conditions": [f"{prefix}:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "payload": {},
            "missing_conditions": [f"{prefix}:json_parse_failed"],
            "warnings": [f"{prefix}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "payload": {},
            "missing_conditions": [f"{prefix}:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }
    return {
        "path": safe_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "payload": payload,
        "missing_conditions": [],
        "warnings": [],
        "secret_detected": _contains_secret_like_payload(payload),
    }


def _load_index(path_value: str | Path | None) -> dict[str, Any]:
    source = _load_json_object(path_value, "closure_index")
    payload = source.get("payload", {}) if isinstance(source.get("payload"), dict) else {}
    missing_conditions = [_sanitize_text(item) for item in source.get("missing_conditions", [])]
    warnings = [_sanitize_text(item) for item in source.get("warnings", [])]
    status = _sanitize_text(payload.get("status") or "skipped") if source.get("loaded") else "skipped"

    if source.get("loaded"):
        missing_conditions.extend(_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions")))
        warnings.extend(_sanitize_text(item) for item in _safe_list(payload.get("warnings")))
        if status == "skipped":
            missing_conditions.append("closure_index:source_status_skipped")
        if status in {"blocked", "failed"}:
            missing_conditions.append(f"closure_index:source_status_{status}")
        if payload.get("read_only") is False:
            missing_conditions.append("closure_index:not_read_only")
        for flag in [
            "real_llm_executed",
            "external_mcp_connected",
            "external_system_connected",
            "deployment_executed",
            "release_created",
            "tag_created",
            "auto_approved",
            "auto_closed",
        ]:
            if bool(payload.get(flag, False)):
                missing_conditions.append(f"closure_index:{flag}_unexpected")
    if source.get("secret_detected"):
        missing_conditions.append("closure_index:secret_like_value_detected")
        warnings.append("closure_index:secret_like_value_detected")

    return {
        **source,
        "status": status,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
    }


def _load_signoff_record(path_value: str | Path | None) -> dict[str, Any]:
    source = _load_json_object(path_value, "manual_signoff_record")
    payload = source.get("payload", {}) if isinstance(source.get("payload"), dict) else {}
    missing_conditions = [_sanitize_text(item) for item in source.get("missing_conditions", [])]
    warnings = [_sanitize_text(item) for item in source.get("warnings", [])]
    roles = payload.get("roles") if isinstance(payload.get("roles"), list) else []
    evidence_acknowledgements = (
        payload.get("evidence_acknowledgements")
        if isinstance(payload.get("evidence_acknowledgements"), list)
        else []
    )
    role_ids = {str(item.get("role") or "").strip() for item in roles if isinstance(item, dict)}
    approved_roles = {
        str(item.get("role") or "").strip()
        for item in roles
        if isinstance(item, dict) and bool(item.get("approved", False))
    }
    accepted_ack_ids = {
        str(item.get("item") or "").strip()
        for item in evidence_acknowledgements
        if isinstance(item, dict) and bool(item.get("accepted", False))
    }

    if source.get("loaded"):
        if payload.get("manual_signoff_completed") is not True:
            missing_conditions.append("manual_signoff_record:not_completed")
        if str(payload.get("decision") or "").strip().lower() != "go":
            missing_conditions.append("manual_signoff_record:decision_not_go")
        for role in REQUIRED_SIGNOFF_ROLES:
            if role not in role_ids:
                missing_conditions.append(f"manual_signoff_record:{role}_missing")
            elif role not in approved_roles:
                missing_conditions.append(f"manual_signoff_record:{role}_not_approved")
        for ack_id in REQUIRED_EVIDENCE_ACKS:
            if ack_id not in accepted_ack_ids:
                missing_conditions.append(f"manual_signoff_record:evidence_ack_{ack_id}_not_accepted")
        if str(payload.get("public_production_direct_launch") or "No-Go").strip().lower() != "no-go":
            missing_conditions.append("manual_signoff_record:public_production_direct_launch_must_remain_no_go")
        if payload.get("auto_signed") is True or payload.get("auto_approved") is True:
            missing_conditions.append("manual_signoff_record:auto_flag_unexpected")
    if source.get("secret_detected"):
        missing_conditions.append("manual_signoff_record:secret_like_value_detected")
        warnings.append("manual_signoff_record:secret_like_value_detected")

    sanitized_record = {
        "decision": _sanitize_text(payload.get("decision") or ""),
        "signed_at": _sanitize_text(payload.get("signed_at") or ""),
        "manual_signoff_completed": payload.get("manual_signoff_completed") is True,
        "public_production_direct_launch": _sanitize_text(payload.get("public_production_direct_launch") or "No-Go"),
        "roles": [
            {
                "role": _sanitize_text(item.get("role") or ""),
                "name": _sanitize_text(item.get("name") or ""),
                "approved": bool(item.get("approved", False)),
                "responsibility": _sanitize_text(item.get("responsibility") or ""),
            }
            for item in roles
            if isinstance(item, dict)
        ],
        "evidence_acknowledgements": [
            {
                "item": _sanitize_text(item.get("item") or ""),
                "accepted": bool(item.get("accepted", False)),
                "note": _sanitize_text(item.get("note") or ""),
            }
            for item in evidence_acknowledgements
            if isinstance(item, dict)
        ],
    }
    return {
        **source,
        "record": sanitized_record if source.get("loaded") else {},
        "missing_conditions": missing_conditions,
        "warnings": warnings,
    }


def _build_signoff_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    latest_summary = payload.get("latest_report_summary") if isinstance(payload.get("latest_report_summary"), dict) else {}
    totals = latest_summary or (payload.get("totals") if isinstance(payload.get("totals"), dict) else {})
    evidence_readiness = (
        latest_summary.get("evidence_readiness_summary")
        if isinstance(latest_summary.get("evidence_readiness_summary"), dict)
        else {}
    )
    reports = _safe_list(payload.get("reports"))
    latest = payload.get("latest_report") or ""
    return [
        {
            "section": "closure_evidence_summary",
            "status": _sanitize_text(payload.get("status") or "skipped"),
            "latest_report": _sanitize_text(latest),
            "report_count": int(payload.get("report_count") or len(reports)),
            "closure_item_count": int(totals.get("closure_item_count") or 0),
            "review_ready_count": int(totals.get("review_ready_count") or 0),
            "evidence_missing_count": int(totals.get("evidence_missing_count") or 0),
            "evidence_incomplete_count": int(totals.get("evidence_incomplete_count") or 0),
            "blocked_closure_count": int(totals.get("blocked_closure_count") or 0),
            "evidence_readiness_summary": {
                "local_evidence_available_count": int(
                    evidence_readiness.get("local_evidence_available_count", 0) or 0
                ),
                "runbook_only_count": int(evidence_readiness.get("runbook_only_count", 0) or 0),
                "missing_count": int(evidence_readiness.get("missing_count", 0) or 0),
                "manual_review_required": bool(evidence_readiness.get("manual_review_required", False)),
                "auto_approved": bool(evidence_readiness.get("auto_approved", False)),
                "auto_closed": bool(evidence_readiness.get("auto_closed", False)),
            },
            "manual_signoff_required": True,
            "auto_signed": False,
        },
        {
            "section": "required_manual_approvals",
            "status": "manual_required",
            "required_roles": list(REQUIRED_SIGNOFF_ROLES),
            "required_decisions": ["Go/No-Go", "rollback_window", "freeze_window", "residual_risk_acceptance"],
            "manual_signoff_required": True,
            "auto_signed": False,
        },
    ]


def _derive_status(index_source: dict[str, Any], signoff_source: dict[str, Any]) -> str:
    if index_source.get("secret_detected") or signoff_source.get("secret_detected"):
        return "blocked"
    if index_source.get("status") in {"blocked", "failed"}:
        return "blocked"
    if any(
        marker in condition
        for condition in index_source.get("missing_conditions", [])
        for marker in ["_unexpected", "not_read_only", "secret_like_value_detected"]
    ):
        return "blocked"
    if any("secret_like_value_detected" in condition for condition in signoff_source.get("missing_conditions", [])):
        return "blocked"
    if not index_source.get("loaded"):
        return "skipped"
    if index_source.get("status") == "skipped":
        return "skipped"
    return "success" if signoff_source.get("loaded") and not signoff_source.get("missing_conditions") else "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.1 人工签核包（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- manual_signoff_required: {payload.get('manual_signoff_required', True)}",
        f"- manual_signoff_completed: {payload.get('manual_signoff_completed', False)}",
        f"- manual_signoff_decision: {payload.get('manual_signoff_decision', '')}",
        "",
        "## Signoff Sections",
    ]
    for item in payload.get("signoff_sections", []):
        lines.append(f"- {item.get('section')}: {item.get('status')}")
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


def build_manual_signoff_package(
    *,
    output_dir: str | Path | None = None,
    closure_index: str | Path | None = None,
    signoff_record: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    index_source = _load_index(closure_index)
    signoff_source = _load_signoff_record(signoff_record)
    status = _derive_status(index_source, signoff_source)
    index_payload = index_source.get("payload", {}) if isinstance(index_source.get("payload"), dict) else {}
    signoff_sections = _build_signoff_sections(index_payload) if index_source.get("loaded") else []
    missing_conditions = sorted(
        set(_sanitize_text(item) for item in index_source.get("missing_conditions", []))
        | set(_sanitize_text(item) for item in signoff_source.get("missing_conditions", []))
    )
    warnings = sorted(
        set(_sanitize_text(item) for item in index_source.get("warnings", []))
        | set(_sanitize_text(item) for item in signoff_source.get("warnings", []))
    )
    record = signoff_source.get("record", {}) if isinstance(signoff_source.get("record"), dict) else {}
    roles = record.get("roles") if isinstance(record.get("roles"), list) else []
    manual_signoff_completed = status == "success" and record.get("manual_signoff_completed") is True

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.1.0-planning",
        "phase": "v4.1_phase_21.3",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "deployment_executed": False,
        "release_created": False,
        "tag_created": False,
        "auto_approved": False,
        "auto_closed": False,
        "manual_signoff_required": True,
        "manual_signoff_completed": manual_signoff_completed,
        "manual_signoff_record_present": bool(signoff_source.get("loaded", False)),
        "manual_signoff_record": record,
        "manual_signoff_roles": [str(item.get("role") or "") for item in roles if isinstance(item, dict)],
        "manual_signoff_decision": str(record.get("decision") or ""),
        "manual_signoff_blockers": missing_conditions,
        "auto_signed": False,
        "closure_index_source": {
            "path": index_source.get("path", ""),
            "provided": index_source.get("provided", False),
            "exists": index_source.get("exists", False),
            "loaded": index_source.get("loaded", False),
            "status": index_source.get("status", "skipped"),
            "secret_detected": index_source.get("secret_detected", False),
        },
        "manual_signoff_record_source": {
            "path": signoff_source.get("path", ""),
            "provided": signoff_source.get("provided", False),
            "exists": signoff_source.get("exists", False),
            "loaded": signoff_source.get("loaded", False),
            "secret_detected": signoff_source.get("secret_detected", False),
        },
        "signoff_sections": signoff_sections,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "人工签核包只提供复核材料和结构化签核记录校验；不自动批准上线，不自动关闭 blocker。",
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_manual_signoff_package"
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
        "manual_signoff_required": True,
        "manual_signoff_completed": manual_signoff_completed,
        "missing_conditions": missing_conditions,
    }


def _evidence_ack_template() -> list[dict[str, Any]]:
    return [
        {
            "item": "real_llm_preflight",
            "accepted": False,
            "latest_report": _latest_real_llm_evidence_path(),
            "note": "确认 OpenAI-compatible 真实 LLM 预检报告为 success，且未输出 API key 原文。",
        },
        {
            "item": "postgres_redis_mcp_smoke",
            "accepted": False,
            "latest_report": _latest_evidence_path(
                DEFAULT_STAGING_SMOKE_DIR,
                "*_real_integration_staging_smoke.json",
            ),
            "note": "确认 PostgreSQL、Redis、external MCP 当前轮 smoke 证据已通过。",
        },
        {
            "item": "business_read_smoke",
            "accepted": False,
            "latest_report": _latest_evidence_path(
                DEFAULT_BUSINESS_SMOKE_DIR,
                "*_business_system_read_smoke.json",
            ),
            "note": "确认业务系统只读 smoke 已通过，且未执行写入。",
        },
        {
            "item": "closure_evidence_review",
            "accepted": False,
            "latest_report": _latest_evidence_path(
                DEFAULT_CLOSURE_WORKFLOW_DIR,
                "*_launch_blocker_closure_workflow.json",
            ),
            "note": "确认 launch blocker closure evidence 已进入人工复核状态。",
        },
    ]


def build_signoff_record_template(*, output_path: str | Path) -> dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "signed_at": "",
        "public_production_direct_launch": "No-Go",
        "auto_signed": False,
        "auto_approved": False,
        "roles": [
            {
                "role": "release_manager",
                "name": "",
                "approved": False,
                "responsibility": "确认发布窗口、回滚方案、变更审批和版本范围。",
            },
            {
                "role": "security_reviewer",
                "name": "",
                "approved": False,
                "responsibility": "确认密钥不泄漏、权限边界、审计证据和安全复核结论。",
            },
            {
                "role": "business_owner",
                "name": "",
                "approved": False,
                "responsibility": "确认业务只读/写入边界、试点范围和残余风险接受。",
            },
            {
                "role": "operations_owner",
                "name": "",
                "approved": False,
                "responsibility": "确认监控、备份恢复、值守和故障处置准备。",
            },
        ],
        "evidence_acknowledgements": _evidence_ack_template(),
        "notes": [
            "填写真实签核人姓名或工号；不要填写 token、API key、数据库连接串或客户敏感数据。",
            "只有人工确认受控试点可进入 Manual-Review 后，才可将 decision 改为 Go 并将四个 approved 改为 true。",
            "public_production_direct_launch 必须保持 No-Go。",
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "success",
        "template_path": str(path),
        "manual_signoff_completed": False,
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.1 人工签核包只读报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--closure-index", default=None)
    parser.add_argument("--signoff-record", default=None)
    parser.add_argument("--write-template", default=None, help="写出人工签核记录 JSON 模板，不生成签核包报告")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.write_template:
        summary = build_signoff_record_template(output_path=args.write_template)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    closure_index, signoff_record = _resolve_cli_default_inputs(
        closure_index=args.closure_index,
        signoff_record=args.signoff_record,
        output_dir=args.output_dir,
    )
    summary = build_manual_signoff_package(
        output_dir=args.output_dir,
        closure_index=closure_index,
        signoff_record=signoff_record,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
