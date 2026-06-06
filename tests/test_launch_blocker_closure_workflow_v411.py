from __future__ import annotations

import json
from pathlib import Path

from scripts.launch_blocker_closure_workflow import build_launch_blocker_closure_workflow


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _blocker_payload(status: str = "partial") -> dict:
    return {
        "status": status,
        "version": "4.0.0-planning",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "auto_approved": False,
        "auto_closed": False,
        "blocker_register": [
            {
                "blocker_id": "LB-001",
                "source_key": "real_llm_production_acceptance_missing",
                "scope": "integration",
                "status": "open",
                "owner": "manual_owner_required",
                "due_at": "manual_due_date_required",
                "approval_state": "not_approved",
            },
            {
                "blocker_id": "LB-002",
                "source_key": "release_gate_change_approval_missing",
                "scope": "release",
                "status": "open",
                "owner": "manual_owner_required",
                "due_at": "manual_due_date_required",
                "approval_state": "not_approved",
            },
        ],
    }


def test_launch_blocker_closure_workflow_default_skips_without_source(tmp_path: Path) -> None:
    summary = build_launch_blocker_closure_workflow(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "4.1.0-planning"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["closure_items"] == []
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "launch_blockers:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_launch_blocker_closure_workflow_marks_missing_evidence_partial(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    _write_json(blockers, _blocker_payload())

    summary = build_launch_blocker_closure_workflow(output_dir=tmp_path / "out", launch_blockers=blockers)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["closure_item_count"] == 2
    assert payload["evidence_missing_count"] == 2
    assert {item["closure_state"] for item in payload["closure_items"]} == {"evidence_missing"}
    assert {item["manual_review_required"] for item in payload["closure_items"]} == {True}
    assert {item["auto_closed"] for item in payload["closure_items"]} == {False}
    assert "real_llm_production_acceptance_missing:closure_evidence_missing" in payload["missing_conditions"]


def test_launch_blocker_closure_workflow_review_ready_does_not_auto_close(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    evidence = tmp_path / "evidence.json"
    _write_json(blockers, _blocker_payload())
    _write_json(
        evidence,
        {
            "status": "partial",
            "read_only": True,
            "evidence_readiness_summary": {
                "local_evidence_available_count": 2,
                "runbook_only_count": 0,
                "missing_count": 0,
                "manual_review_required": True,
                "auto_approved": False,
                "auto_closed": False,
            },
            "closure_items": [
                {
                    "source_key": "real_llm_production_acceptance_missing",
                    "owner": "platform-owner",
                    "due_at": "2026-06-10",
                    "compensating_controls": ["真实 LLM opt-in 验收报告已归档"],
                    "closure_evidence_refs": ["docs/reports/redacted-real-llm-acceptance.json"],
                    "reviewer": "release-manager",
                    "approval_state": "pending_review",
                },
                {
                    "blocker_id": "LB-002",
                    "owner": "release-owner",
                    "due_at": "2026-06-10",
                    "compensating_controls": ["变更审批单已归档"],
                    "closure_evidence_refs": ["docs/reports/redacted-change-ticket.json"],
                    "reviewer": "release-manager",
                    "approval_state": "approved",
                },
            ],
        },
    )

    summary = build_launch_blocker_closure_workflow(
        output_dir=tmp_path / "out",
        launch_blockers=blockers,
        closure_evidence=evidence,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["review_ready_count"] == 2
    assert payload["evidence_readiness_summary"]["local_evidence_available_count"] == 2
    assert payload["evidence_readiness_summary"]["manual_review_required"] is True
    assert payload["evidence_readiness_summary"]["auto_approved"] is False
    assert {item["closure_state"] for item in payload["closure_items"]} == {"review_ready"}
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert {item["auto_closed"] for item in payload["closure_items"]} == {False}
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_launch_blocker_closure_workflow_incomplete_evidence_remains_partial(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    evidence = tmp_path / "evidence.json"
    _write_json(blockers, _blocker_payload())
    _write_json(
        evidence,
        {
            "status": "partial",
            "read_only": True,
            "closure_items": [
                {
                    "source_key": "real_llm_production_acceptance_missing",
                    "owner": "platform-owner",
                    "approval_state": "not_approved",
                }
            ],
        },
    )

    summary = build_launch_blocker_closure_workflow(
        output_dir=tmp_path / "out",
        launch_blockers=blockers,
        closure_evidence=evidence,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    states = {item["source_key"]: item["closure_state"] for item in payload["closure_items"]}
    assert states["real_llm_production_acceptance_missing"] == "evidence_incomplete"
    assert states["release_gate_change_approval_missing"] == "evidence_missing"
    assert "real_llm_production_acceptance_missing:due_at_missing" in payload["missing_conditions"]
    assert "real_llm_production_acceptance_missing:approval_state_not_ready" in payload["missing_conditions"]


def test_launch_blocker_closure_workflow_blocks_rejected_evidence(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    evidence = tmp_path / "evidence.json"
    _write_json(blockers, _blocker_payload())
    _write_json(
        evidence,
        {
            "status": "partial",
            "read_only": True,
            "closure_items": [
                {
                    "source_key": "real_llm_production_acceptance_missing",
                    "owner": "platform-owner",
                    "due_at": "2026-06-10",
                    "compensating_controls": ["control"],
                    "closure_evidence_refs": ["docs/reports/redacted.json"],
                    "reviewer": "release-manager",
                    "approval_state": "rejected",
                }
            ],
        },
    )

    summary = build_launch_blocker_closure_workflow(
        output_dir=tmp_path / "out",
        launch_blockers=blockers,
        closure_evidence=evidence,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["blocked_closure_count"] == 1
    assert "real_llm_production_acceptance_missing:approval_rejected" in payload["missing_conditions"]
    assert payload["go_no_go"]["recommendation"] == "No-Go"


def test_launch_blocker_closure_workflow_blocks_secret_like_input_without_leak(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    evidence = tmp_path / "evidence.json"
    key_value = "sk-" + "closure-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(blockers, _blocker_payload())
    _write_json(
        evidence,
        {
            "status": "partial",
            "read_only": True,
            "api_key": key_value,
            "DATABASE_URL": db_url,
            "closure_items": [],
        },
    )

    summary = build_launch_blocker_closure_workflow(
        output_dir=tmp_path / "out",
        launch_blockers=blockers,
        closure_evidence=evidence,
    )
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "closure_evidence:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_launch_blocker_closure_workflow_blocks_unexpected_real_execution_flags(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    _write_json(
        blockers,
        {
            **_blocker_payload(),
            "read_only": False,
            "real_llm_executed": True,
            "external_mcp_connected": True,
            "external_system_connected": True,
            "release_created": True,
            "tag_created": True,
            "auto_approved": True,
            "auto_closed": True,
        },
    )

    summary = build_launch_blocker_closure_workflow(output_dir=tmp_path / "out", launch_blockers=blockers)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["external_system_connected"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert "launch_blockers:not_read_only" in payload["missing_conditions"]
    assert "launch_blockers:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "launch_blockers:auto_approved_unexpected" in payload["missing_conditions"]
    assert "launch_blockers:auto_closed_unexpected" in payload["missing_conditions"]


def test_launch_blocker_closure_workflow_preserves_skipped_source(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    payload = _blocker_payload(status="skipped")
    for item in payload["blocker_register"]:
        item["status"] = "skipped"
    _write_json(blockers, payload)

    summary = build_launch_blocker_closure_workflow(output_dir=tmp_path / "out", launch_blockers=blockers)
    report = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert {item["closure_state"] for item in report["closure_items"]} == {"skipped"}
    assert "launch_blockers:source_status_skipped" in report["missing_conditions"]
