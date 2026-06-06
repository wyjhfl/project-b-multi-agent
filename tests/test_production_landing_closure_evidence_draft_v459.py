from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_closure_evidence_draft import build_production_landing_closure_evidence_draft
from scripts.production_landing_input_readiness import build_production_landing_input_readiness


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_closure_evidence_draft_prefills_refs_without_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.production_landing_closure_evidence_draft.ROOT_DIR", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "business_system_read_smoke_v45.md").write_text("safe", encoding="utf-8")
    (tmp_path / "docs" / "reports" / "business_system_read_smoke").mkdir(parents=True)
    register = tmp_path / "launch_blockers.json"
    _write_json(
        register,
        {
            "status": "partial",
            "blocker_register": [
                {"blocker_id": "LB-001", "source_key": "business_system_integration_acceptance_missing"},
            ],
        },
    )

    summary = build_production_landing_closure_evidence_draft(
        launch_blockers=register,
        output_path=tmp_path / "closure_evidence.draft.json",
    )
    payload = json.loads(Path(summary["draft_path"]).read_text(encoding="utf-8"))
    item = payload["closure_items"][0]

    assert summary["status"] == "success"
    assert payload["draft_only"] is True
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert item["approval_state"] == "pending_review"
    assert item["owner"] == "integration_owner"
    assert item["reviewer"] == "business_reviewer"
    assert item["due_at"] == item["manual_fill_guidance"]["suggested_due_at"]
    assert item["evidence_readiness"]["status"] == "local_evidence_available"
    assert item["evidence_readiness"]["has_report_ref"] is True
    assert item["evidence_readiness"]["manual_review_required"] is True
    assert item["review_recommendation"].startswith("已有本地报告或证据目录")
    assert item["manual_fill_guidance"]["suggested_owner_role"] == "integration_owner"
    assert item["manual_fill_guidance"]["suggested_reviewer_role"] == "business_reviewer"
    assert item["manual_fill_guidance"]["suggested_due_at"]
    assert item["manual_fill_guidance"]["required_manual_fields"] == ["owner", "due_at", "reviewer", "approval_state"]
    assert item["manual_fill_guidance"]["approval_state_allowed_values"] == ["pending_review", "approved"]
    assert "docs/business_system_read_smoke_v45.md" in item["closure_evidence_refs"]
    assert payload["role_assignment_summary"]["owner_role_counts"]["integration_owner"] == 1
    assert payload["role_assignment_summary"]["reviewer_role_counts"]["business_reviewer"] == 1
    assert payload["role_assignment_summary"]["manual_due_at_assignment_required"] is True
    assert payload["evidence_readiness_summary"]["local_evidence_available_count"] == 1
    assert payload["evidence_readiness_summary"]["runbook_only_count"] == 0
    assert payload["evidence_readiness_summary"]["missing_count"] == 0
    assert payload["evidence_readiness_summary"]["auto_approved"] is False
    assert payload["evidence_readiness_summary"]["auto_closed"] is False
    assert summary["prefilled_evidence_ref_count"] >= 1


def test_closure_evidence_draft_reduces_input_readiness_gaps_without_becoming_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.production_landing_closure_evidence_draft.ROOT_DIR", tmp_path)
    (tmp_path / "docs" / "business_system_read_smoke_v45.md").parent.mkdir(parents=True)
    (tmp_path / "docs" / "business_system_read_smoke_v45.md").write_text("safe", encoding="utf-8")
    register = tmp_path / "launch_blockers.json"
    _write_json(
        register,
        {
            "status": "partial",
            "blocker_register": [
                {"blocker_id": "LB-001", "source_key": "business_system_integration_acceptance_missing"},
            ],
        },
    )
    draft = tmp_path / "closure_evidence.draft.json"
    build_production_landing_closure_evidence_draft(launch_blockers=register, output_path=draft)

    business_env = tmp_path / "business.env"
    business_env.write_text(
        "BUSINESS_INTEGRATION_ENABLED=true\n"
        "BUSINESS_INTEGRATION_READ_ONLY=true\n"
        "BUSINESS_INTEGRATION_WRITE_ENABLED=false\n"
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true\n"
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true\n"
        "BUSINESS_SYSTEM_NAME=<system-name>\n"
        "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL\n"
        "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN\n"
        "BUSINESS_SYSTEM_BASE_URL=<https://business-system.example.com>\n"
        "BUSINESS_SYSTEM_TOKEN=<set-in-local-env-only>\n"
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe\n",
        encoding="utf-8",
    )
    signoff = tmp_path / "signoff.json"
    _write_json(
        signoff,
        {
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [],
        },
    )

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=draft,
        manual_signoff=signoff,
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    closure = next(item for item in payload["inputs"] if item["input_id"] == "launch_blocker_closure_evidence")

    assert summary["status"] == "partial"
    assert closure["status"] == "ready"
    assert closure["closure_item_count"] == 1
    assert closure["ready_count"] == 1
    assert closure["missing_conditions"] == []
    assert "next_action" not in closure


def test_closure_evidence_draft_does_not_write_secret_like_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.production_landing_closure_evidence_draft.ROOT_DIR", tmp_path)
    register = tmp_path / "launch_blockers.json"
    _write_json(
        register,
        {
            "status": "partial",
            "blocker_register": [
                {"blocker_id": "LB-001", "source_key": "real_llm_production_acceptance_missing"},
            ],
        },
    )

    summary = build_production_landing_closure_evidence_draft(
        launch_blockers=register,
        output_path=tmp_path / "closure_evidence.draft.json",
    )
    merged = Path(summary["draft_path"]).read_text(encoding="utf-8")

    assert "sk-" not in merged
    assert "tp-" not in merged
    assert "bearer " not in merged.lower()
    assert "token=" not in merged.lower()


def test_closure_evidence_draft_marks_runbook_only_and_missing_refs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.production_landing_closure_evidence_draft.ROOT_DIR", tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "release_gate_rollback_governance_pack_v39.md").write_text("safe", encoding="utf-8")
    register = tmp_path / "launch_blockers.json"
    _write_json(
        register,
        {
            "status": "partial",
            "blocker_register": [
                {"blocker_id": "LB-001", "source_key": "rollback_drill_and_freeze_window_missing"},
                {"blocker_id": "LB-002", "source_key": "unknown_missing"},
            ],
        },
    )

    summary = build_production_landing_closure_evidence_draft(
        launch_blockers=register,
        output_path=tmp_path / "closure_evidence.draft.json",
    )
    payload = json.loads(Path(summary["draft_path"]).read_text(encoding="utf-8"))
    first, second = payload["closure_items"]

    assert first["evidence_readiness"]["status"] == "runbook_only"
    assert first["review_recommendation"].startswith("仅有 runbook")
    assert second["evidence_readiness"]["status"] == "missing"
    assert second["review_recommendation"].startswith("补充可人工复核")
    assert payload["evidence_readiness_summary"]["local_evidence_available_count"] == 0
    assert payload["evidence_readiness_summary"]["runbook_only_count"] == 1
    assert payload["evidence_readiness_summary"]["missing_count"] == 1
    assert payload["evidence_readiness_summary"]["manual_review_required"] is True
