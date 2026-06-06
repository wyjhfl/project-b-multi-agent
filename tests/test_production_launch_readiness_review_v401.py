from __future__ import annotations

import json
from pathlib import Path

from scripts.production_launch_readiness_review import build_production_launch_readiness_review


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_launch_readiness_default_is_partial_and_manual_review(tmp_path: Path) -> None:
    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["version"] == "4.0.0-planning"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["deployment_executed"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "real_llm_production_acceptance_missing" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_launch_readiness_loads_success_sources_but_keeps_manual_review(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    closeout = tmp_path / "closeout.json"
    release_gate = tmp_path / "release_gate.json"
    _write_json(evidence, {"status": "success", "version": "3.9.0", "read_only": True, "real_llm_executed": False})
    _write_json(closeout, {"status": "success", "version": "3.9.0", "read_only": True, "real_llm_executed": False})
    _write_json(release_gate, {"status": "success", "version": "3.9.0", "read_only": True, "real_llm_executed": False})

    summary = build_production_launch_readiness_review(
        output_dir=tmp_path / "out",
        evidence_archive=evidence,
        pilot_closeout=closeout,
        release_gate=release_gate,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["loaded_source_count"] == 3
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["auto_changed"] is False
    assert "external_security_scan_and_signoff_missing" in payload["missing_conditions"]


def test_launch_readiness_preserves_skipped_source_semantics(tmp_path: Path) -> None:
    compliance = tmp_path / "compliance.json"
    _write_json(
        compliance,
        {
            "status": "skipped",
            "version": "3.9.0",
            "read_only": True,
            "real_llm_executed": False,
            "skipped_reasons": ["formal_security_signoff_missing"],
        },
    )

    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out", compliance_baseline=compliance)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert "compliance_baseline:source_status_skipped" in payload["missing_conditions"]
    assert "formal_security_signoff_missing" in payload["missing_conditions"]
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_launch_readiness_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    key_value = "sk-" + "should-not-leak"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        source,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "api_key": key_value,
            "token": "plain-json-token",
            "DATABASE_URL": db_url,
        },
    )

    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out", evidence_archive=source)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert payload["go_no_go"]["controlled_internal_pilot"] == "No-Go"
    assert "evidence_archive:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert "plain-json-token" not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_launch_readiness_blocks_unexpected_real_execution(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _write_json(
        source,
        {
            "status": "success",
            "read_only": False,
            "real_llm_executed": True,
            "external_mcp_connected": True,
            "external_system_connected": True,
            "release_created": True,
            "tag_created": True,
        },
    )

    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out", controlled_integration=source)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert "controlled_integration:not_read_only" in payload["missing_conditions"]
    assert "controlled_integration:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "controlled_integration:external_mcp_connected_unexpected" in payload["missing_conditions"]
    assert "controlled_integration:external_system_connected_unexpected" in payload["missing_conditions"]


def test_launch_readiness_blocks_upstream_blocked_or_failed_status(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _write_json(
        source,
        {
            "status": "blocked",
            "read_only": True,
            "real_llm_executed": False,
            "missing_conditions": ["upstream:blocker"],
        },
    )

    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out", security_regression=source)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert payload["go_no_go"]["controlled_internal_pilot"] == "No-Go"
    assert "upstream:blocker" in payload["missing_conditions"]


def test_launch_readiness_skips_when_provided_source_cannot_load(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    summary = build_production_launch_readiness_review(output_dir=tmp_path / "out", evidence_archive=missing)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["controlled_internal_pilot"] == "Needs-Input"
    assert "evidence_archive:path_not_found" in payload["missing_conditions"]
