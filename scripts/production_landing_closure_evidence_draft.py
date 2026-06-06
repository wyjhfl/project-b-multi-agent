from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure" / "closure_evidence.draft.json"
DEFAULT_REVIEW_DUE_DAYS = 7

EVIDENCE_HINTS = {
    "backup_restore_dr_failover_evidence_missing": {
        "owner": "sre_owner_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["使用备份恢复与 DR 只读证据包作为人工复核材料；生产 failover 仍需人工演练记录。"],
        "refs": [
            "docs/backup_restore_dr_evidence_pack_v38.md",
            "docs/reports/store_redis_readiness_drill",
        ],
    },
    "business_system_integration_acceptance_missing": {
        "owner": "integration_owner_required",
        "reviewer": "business_reviewer_required",
        "controls": ["仅允许只读 business_read_probe；真实业务系统读 smoke 必须使用本地环境变量并保持写入关闭。"],
        "refs": [
            "docs/business_system_read_smoke_v45.md",
            "docs/business_system_integration_safety_checklist_v37.md",
            "docs/reports/business_system_read_smoke",
        ],
    },
    "capacity_load_soak_test_evidence_missing": {
        "owner": "sre_owner_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["容量与 soak 测试需独立窗口执行；当前仅提供只读 readiness plan 和本地工程证据。"],
        "refs": [
            "docs/capacity_load_test_readiness_plan_v38.md",
            "docs/reports/frontend_production_build",
            "docs/reports/production_runtime_smoke",
        ],
    },
    "external_mcp_production_acceptance_missing": {
        "owner": "integration_owner_required",
        "reviewer": "security_reviewer_required",
        "controls": ["真实 MCP 必须经过 command allowlist、tool allowlist、ToolGateway、PolicyEngine、审批和审计链路。"],
        "refs": [
            "docs/real_integration_staging_smoke_v44.md",
            "docs/real_integration_staging_gate_v44.md",
            "docs/reports/external_mcp_acceptance_gate",
            "docs/reports/real_integration_staging_smoke",
        ],
    },
    "external_security_scan_and_signoff_missing": {
        "owner": "security_owner_required",
        "reviewer": "security_reviewer_required",
        "controls": ["安全扫描和合规签核必须由人工/外部工具执行；当前只提供安全基线和回归证据索引。"],
        "refs": [
            "docs/compliance_security_baseline_v39.md",
            "docs/security_regression_compliance_evidence_pack_v39.md",
            "docs/reports/production_auth_rbac_acceptance",
        ],
    },
    "postgres_redis_production_acceptance_missing": {
        "owner": "platform_owner_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["PostgreSQL/Redis 生产验收需受控 smoke、迁移、故障恢复和观测证据；默认仍不宣称完成。"],
        "refs": [
            "docs/store_redis_readiness_drill_v37.md",
            "docs/real_integration_staging_smoke_v44.md",
            "docs/reports/store_redis_readiness_drill",
            "docs/reports/real_integration_staging_smoke",
        ],
    },
    "production_sso_oidc_signoff_missing": {
        "owner": "security_owner_required",
        "reviewer": "business_reviewer_required",
        "controls": ["OIDC/SSO 当前为最小接入骨架；生产 IdP 签核和用户生命周期仍需人工确认。"],
        "refs": [
            "docs/compliance_security_baseline_v39.md",
            "docs/reports/production_auth_rbac_acceptance",
        ],
    },
    "real_llm_production_acceptance_missing": {
        "owner": "ai_platform_owner_required",
        "reviewer": "security_reviewer_required",
        "controls": ["真实 LLM 调用必须 opt-in，保持预算、缓存、fallback、审计和脱敏证据；不得输出 API key。"],
        "refs": [
            "docs/xiaomi_openai_compatible_llm_integration_v45.md",
            "docs/real_llm_provider_acceptance_gate_v37.md",
            "docs/reports/real_llm_provider_acceptance_gate",
            "docs/reports/real_llm_pilot",
        ],
    },
    "release_gate_change_approval_missing": {
        "owner": "release_manager_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["发布变更需要独立 CAB/变更审批；脚本只生成只读门禁材料，不创建 release/tag。"],
        "refs": [
            "docs/release_gate_rollback_governance_pack_v39.md",
            "docs/production_runbook_finalization_v40.md",
            "docs/reports/production_launch_readiness",
        ],
    },
    "rollback_drill_and_freeze_window_missing": {
        "owner": "release_manager_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["回滚与冻结窗口需人工演练确认；当前仅提供 runbook 级证据和只读治理材料。"],
        "refs": [
            "docs/release_gate_rollback_governance_pack_v39.md",
            "docs/production_runbook_finalization_v40.md",
        ],
    },
    "secret_rotation_leakage_response_drill_missing": {
        "owner": "security_owner_required",
        "reviewer": "security_reviewer_required",
        "controls": ["密钥轮换和泄漏响应需人工演练；仓库报告必须保持 secret 原文不输出。"],
        "refs": [
            "docs/secret_rotation_leakage_response_pack_v39.md",
            "docs/reports/production_landing_input_readiness",
        ],
    },
    "sre_apm_alerting_oncall_acceptance_missing": {
        "owner": "sre_owner_required",
        "reviewer": "operations_reviewer_required",
        "controls": ["APM/告警/on-call 接入需真实平台验收；当前仅提供 SRE 基线和运行时 smoke 证据。"],
        "refs": [
            "docs/sre_observability_baseline_v38.md",
            "docs/slo_alerting_runbook_pack_v38.md",
            "docs/reports/production_runtime_smoke",
        ],
    },
    "tenant_isolation_production_acceptance_missing": {
        "owner": "security_owner_required",
        "reviewer": "business_reviewer_required",
        "controls": ["多租户隔离仍需生产级验收；当前仅提供 RBAC、审计和边界说明证据。"],
        "refs": [
            "docs/compliance_security_baseline_v39.md",
            "docs/reports/production_auth_rbac_acceptance",
        ],
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _load_register(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("launch blocker register must be a JSON object")
    return payload


def _ref_exists(ref: str) -> bool:
    path = ROOT_DIR / ref
    return path.exists()


def _suggest_due_at(generated_at: str, days: int = DEFAULT_REVIEW_DUE_DAYS) -> str:
    base = datetime.fromisoformat(generated_at)
    return (base.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)).date().isoformat()


def _manual_fill_guidance(*, owner: str, reviewer: str, suggested_due_at: str, refs: list[str]) -> dict[str, Any]:
    return {
        "suggested_owner_role": owner,
        "suggested_reviewer_role": reviewer,
        "suggested_due_at": suggested_due_at,
        "required_manual_fields": ["owner", "due_at", "reviewer", "approval_state"],
        "approval_state_allowed_values": ["pending_review", "approved"],
        "prefilled_evidence_ref_count": len([ref for ref in refs if ref != "manual_closure_evidence_required"]),
        "next_human_action": "确认 owner/reviewer/due_at，复核证据引用后将 approval_state 调整为 pending_review 或 approved。",
    }


def _role_assignment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    owner_roles: dict[str, int] = {}
    reviewer_roles: dict[str, int] = {}
    for item in rows:
        guidance = item.get("manual_fill_guidance") if isinstance(item.get("manual_fill_guidance"), dict) else {}
        owner = str(guidance.get("suggested_owner_role") or item.get("owner") or "")
        reviewer = str(guidance.get("suggested_reviewer_role") or item.get("reviewer") or "")
        owner_roles[owner] = owner_roles.get(owner, 0) + 1
        reviewer_roles[reviewer] = reviewer_roles.get(reviewer, 0) + 1
    return {
        "owner_role_counts": dict(sorted(owner_roles.items())),
        "reviewer_role_counts": dict(sorted(reviewer_roles.items())),
        "manual_owner_assignment_required": True,
        "manual_reviewer_assignment_required": True,
        "manual_due_at_assignment_required": True,
        "auto_approved": False,
        "auto_closed": False,
    }


def _evidence_readiness(refs: list[str]) -> dict[str, Any]:
    effective_refs = [ref for ref in refs if ref != "manual_closure_evidence_required"]
    has_report_ref = any(ref.startswith("docs/reports/") for ref in effective_refs)
    if not effective_refs:
        status = "missing"
        recommendation = "补充可人工复核的脱敏证据引用后再进入签核。"
    elif has_report_ref:
        status = "local_evidence_available"
        recommendation = "已有本地报告或证据目录，可进入人工复核；不得视为自动关闭。"
    else:
        status = "runbook_only"
        recommendation = "仅有 runbook 或计划文档，需要补充当前轮执行证据。"
    return {
        "status": status,
        "evidence_ref_count": len(effective_refs),
        "has_report_ref": has_report_ref,
        "manual_review_required": True,
        "review_recommendation": recommendation,
    }


def _evidence_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [
        item.get("evidence_readiness", {}).get("status")
        for item in rows
        if isinstance(item.get("evidence_readiness"), dict)
    ]
    return {
        "local_evidence_available_count": statuses.count("local_evidence_available"),
        "runbook_only_count": statuses.count("runbook_only"),
        "missing_count": statuses.count("missing"),
        "manual_review_required": True,
        "auto_approved": False,
        "auto_closed": False,
    }


def _review_queue(value: str, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    return text.removesuffix("_required") or fallback


def _initial_review_state(evidence_readiness: dict[str, Any]) -> str:
    return "not_approved" if evidence_readiness.get("status") == "missing" else "pending_review"


def build_production_landing_closure_evidence_draft(
    *,
    launch_blockers: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    source = _load_register(launch_blockers)
    blockers = source.get("blocker_register") if isinstance(source.get("blocker_register"), list) else []
    output = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    suggested_due_at = _suggest_due_at(generated_at)

    rows: list[dict[str, Any]] = []
    for item in blockers:
        if not isinstance(item, dict):
            continue
        source_key = str(item.get("source_key") or "")
        hint = EVIDENCE_HINTS.get(source_key, {})
        refs = [ref for ref in hint.get("refs", []) if _ref_exists(str(ref))]
        owner = _review_queue(str(hint.get("owner") or ""), "manual_owner")
        reviewer = _review_queue(str(hint.get("reviewer") or ""), "manual_reviewer")
        evidence_readiness = _evidence_readiness(refs or ["manual_closure_evidence_required"])
        approval_state = _initial_review_state(evidence_readiness)
        rows.append(
            {
                "blocker_id": str(item.get("blocker_id") or ""),
                "source_key": source_key,
                "owner": owner,
                "due_at": suggested_due_at if approval_state == "pending_review" else "manual_due_date_required",
                "compensating_controls": list(hint.get("controls") or ["manual_compensating_controls_required"]),
                "closure_evidence_refs": refs or ["manual_closure_evidence_required"],
                "evidence_readiness": evidence_readiness,
                "review_recommendation": evidence_readiness["review_recommendation"],
                "reviewer": reviewer,
                "approval_state": approval_state,
                "draft_only": True,
                "manual_fill_guidance": _manual_fill_guidance(
                    owner=owner,
                    reviewer=reviewer,
                    suggested_due_at=suggested_due_at,
                    refs=refs or ["manual_closure_evidence_required"],
                ),
                "notes": [
                    "该草案仅预填脱敏证据引用和补偿控制，便于人工复核。",
                    "due_at 与 approval_state 必须由人工填写；草案不会自动关闭 blocker。",
                ],
            }
        )

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.9",
        "phase": "v4.5 Phase 25.11 Production Landing Closure Evidence Draft",
        "status": "partial",
        "read_only": True,
        "draft_only": True,
        "auto_approved": False,
        "auto_closed": False,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "business_system_connected": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "closure_items": rows,
        "closure_item_count": len(rows),
        "role_assignment_summary": _role_assignment_summary(rows),
        "prefilled_evidence_ref_count": sum(
            len([ref for ref in item.get("closure_evidence_refs", []) if ref != "manual_closure_evidence_required"])
            for item in rows
        ),
        "evidence_readiness_summary": _evidence_readiness_summary(rows),
        "source_register": str(Path(launch_blockers)),
        "public_production_direct_launch": "No-Go",
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "success",
        "draft_path": str(output),
        "closure_item_count": len(rows),
        "prefilled_evidence_ref_count": payload["prefilled_evidence_ref_count"],
        "auto_approved": False,
        "auto_closed": False,
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地 closure evidence 只读草案，不自动批准。")
    parser.add_argument("--launch-blockers", required=True)
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_closure_evidence_draft(
        launch_blockers=args.launch_blockers,
        output_path=args.output_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
