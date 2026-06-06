from __future__ import annotations

import json
from pathlib import Path

from scripts.production_runbook_finalization import build_production_runbook_finalization


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_runbook_finalization_default_partial_or_skipped(tmp_path: Path) -> None:
    summary = build_production_runbook_finalization(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "4.0.0-planning"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["deployment_executed"] is False
    assert payload["rollback_executed"] is False
    assert payload["alert_sent"] is False
    assert payload["oncall_notified"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert payload["runbook_count"] >= 20
    assert "launch_readiness:input_not_provided" in payload["missing_conditions"]
    assert "launch_blockers:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_production_runbook_finalization_loads_sources_and_keeps_manual_review(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    blockers = tmp_path / "blockers.json"
    _write_json(readiness, {"status": "partial", "read_only": True, "real_llm_executed": False, "missing_conditions": ["launch:manual"]})
    _write_json(
        blockers,
        {
            "status": "partial",
            "read_only": True,
            "real_llm_executed": False,
            "blocker_count": 3,
            "open_blocker_count": 2,
            "blocked_blocker_count": 1,
            "skipped_blocker_count": 0,
            "go_no_go": {"recommendation": "Manual-Review", "production_direct_launch": "No-Go"},
        },
    )

    summary = build_production_runbook_finalization(
        output_dir=tmp_path / "out",
        launch_readiness=readiness,
        launch_blockers=blockers,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert "launch:manual" in payload["missing_conditions"]
    assert {item["loaded"] for item in payload["input_sources"]} == {True}
    assert payload["blocker_summary"]["blocker_count"] == 3
    assert payload["blocker_summary"]["open_blocker_count"] == 2
    assert payload["blocker_summary"]["blocked_blocker_count"] == 1
    assert payload["blocker_summary"]["go_no_go"]["production_direct_launch"] == "No-Go"


def test_production_runbook_finalization_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    key_value = "sk-" + "should-not-leak"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        readiness,
        {
            "status": "partial",
            "read_only": True,
            "real_llm_executed": False,
            "token": "plain-json-token",
            "api_key": key_value,
            "DATABASE_URL": db_url,
        },
    )

    summary = build_production_runbook_finalization(output_dir=tmp_path / "out", launch_readiness=readiness)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "launch_readiness:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert "plain-json-token" not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_production_runbook_finalization_blocks_unexpected_real_execution(tmp_path: Path) -> None:
    blockers = tmp_path / "blockers.json"
    _write_json(
        blockers,
        {
            "status": "success",
            "read_only": False,
            "real_llm_executed": True,
            "external_mcp_connected": True,
            "external_system_connected": True,
            "deployment_executed": True,
            "rollback_executed": True,
            "security_scan_executed": True,
            "secret_rotation_executed": True,
            "auto_approved": True,
            "auto_closed": True,
        },
    )

    summary = build_production_runbook_finalization(output_dir=tmp_path / "out", launch_blockers=blockers)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["external_system_connected"] is False
    assert payload["deployment_executed"] is False
    assert payload["rollback_executed"] is False
    assert payload["security_scan_executed"] is False
    assert payload["secret_rotation_executed"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert "launch_blockers:not_read_only" in payload["missing_conditions"]
    assert "launch_blockers:deployment_executed_unexpected" in payload["missing_conditions"]
    assert "launch_blockers:auto_approved_unexpected" in payload["missing_conditions"]


def test_production_runbook_finalization_skips_when_source_cannot_load(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    summary = build_production_runbook_finalization(output_dir=tmp_path / "out", launch_readiness=missing)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert "launch_readiness:path_not_found" in payload["missing_conditions"]
    source = next(item for item in payload["input_sources"] if item["name"] == "launch_readiness")
    assert source["loaded"] is False
