from __future__ import annotations

import json
from pathlib import Path

from scripts.launch_blocker_register import build_launch_blocker_register


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_launch_blocker_register_default_is_skipped_without_auto_approval(tmp_path: Path) -> None:
    summary = build_launch_blocker_register(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "4.0.0-planning"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert {item["status"] for item in payload["blocker_register"]} == {"skipped"}
    assert {item["approval_state"] for item in payload["blocker_register"]} == {"not_approved"}
    assert "launch_readiness:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_launch_blocker_register_builds_open_register_from_launch_readiness(tmp_path: Path) -> None:
    review = tmp_path / "launch.json"
    _write_json(
        review,
        {
            "status": "partial",
            "version": "4.0.0-planning",
            "read_only": True,
            "real_llm_executed": False,
            "external_mcp_connected": False,
            "production_blockers": [
                "real_llm_production_acceptance_missing",
                "release_gate_change_approval_missing",
            ],
            "missing_conditions": ["custom_launch_blocker_missing"],
        },
    )

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=review)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["open_blocker_count"] == payload["blocker_count"]
    assert "custom_launch_blocker_missing" in {item["source_key"] for item in payload["blocker_register"]}
    assert {item["owner"] for item in payload["blocker_register"]} == {"manual_owner_required"}
    assert {item["due_at"] for item in payload["blocker_register"]} == {"manual_due_date_required"}
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"


def test_launch_blocker_register_blocks_upstream_blocked_status(tmp_path: Path) -> None:
    review = tmp_path / "launch.json"
    _write_json(
        review,
        {
            "status": "blocked",
            "read_only": True,
            "real_llm_executed": False,
            "production_blockers": ["external_security_scan_and_signoff_missing"],
            "missing_conditions": ["upstream:blocker"],
        },
    )

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=review)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "launch_readiness:source_status_blocked" in payload["missing_conditions"]
    assert {item["status"] for item in payload["blocker_register"]} == {"blocked"}


def test_launch_blocker_register_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    review = tmp_path / "launch.json"
    key_value = "sk-" + "should-not-leak"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        review,
        {
            "status": "partial",
            "read_only": True,
            "real_llm_executed": False,
            "token": "plain-json-token",
            "api_key": key_value,
            "DATABASE_URL": db_url,
        },
    )

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=review)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "launch_readiness:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert "plain-json-token" not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_launch_blocker_register_blocks_unexpected_real_execution(tmp_path: Path) -> None:
    review = tmp_path / "launch.json"
    _write_json(
        review,
        {
            "status": "success",
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

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=review)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["external_system_connected"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert "launch_readiness:not_read_only" in payload["missing_conditions"]
    assert "launch_readiness:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "launch_readiness:external_mcp_connected_unexpected" in payload["missing_conditions"]
    assert "launch_readiness:auto_approved_unexpected" in payload["missing_conditions"]
    assert "launch_readiness:auto_closed_unexpected" in payload["missing_conditions"]


def test_launch_blocker_register_skips_when_source_cannot_load(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=missing)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["launch_readiness_source"]["loaded"] is False
    assert {item["status"] for item in payload["blocker_register"]} == {"skipped"}
    assert "launch_readiness:path_not_found" in payload["missing_conditions"]


def test_launch_blocker_register_preserves_loaded_skipped_source(tmp_path: Path) -> None:
    review = tmp_path / "launch.json"
    _write_json(
        review,
        {
            "status": "skipped",
            "read_only": True,
            "real_llm_executed": False,
            "missing_conditions": ["manual_evidence_missing"],
        },
    )

    summary = build_launch_blocker_register(output_dir=tmp_path / "out", launch_readiness=review)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["launch_readiness_source"]["loaded"] is True
    assert {item["status"] for item in payload["blocker_register"]} == {"skipped"}
    assert "launch_readiness:source_status_skipped" in payload["missing_conditions"]
    assert "manual_evidence_missing" in payload["missing_conditions"]
