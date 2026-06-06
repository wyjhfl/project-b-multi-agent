from __future__ import annotations

import json
from pathlib import Path

from scripts.closure_evidence_index import build_closure_evidence_index


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _closure_report(**overrides: object) -> dict:
    payload = {
        "status": "partial",
        "version": "4.1.0-planning",
        "phase": "v4.1_phase_21.1",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "auto_approved": False,
        "auto_closed": False,
        "go_no_go": {"production_direct_launch": "No-Go"},
        "closure_item_count": 2,
        "review_ready_count": 1,
        "evidence_missing_count": 1,
        "evidence_incomplete_count": 0,
        "blocked_closure_count": 0,
        "skipped_closure_count": 0,
        "evidence_readiness_summary": {
            "local_evidence_available_count": 1,
            "runbook_only_count": 1,
            "missing_count": 0,
            "manual_review_required": True,
            "auto_approved": False,
            "auto_closed": False,
        },
        "closure_items": [
            {"blocker_id": "LB-001", "closure_state": "review_ready"},
            {"blocker_id": "LB-002", "closure_state": "evidence_missing"},
        ],
    }
    payload.update(overrides)
    return payload


def test_closure_evidence_index_skips_when_input_missing(tmp_path: Path) -> None:
    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=tmp_path / "missing")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["report_count"] == 0
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "input_dir_not_found" in payload["warnings"][0]
    assert Path(summary["markdown_path"]).exists()


def test_closure_evidence_index_indexes_closure_workflow_reports(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    _write_json(source / "2026_demo_launch_blocker_closure_workflow.json", _closure_report())

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["report_count"] == 1
    assert payload["totals"]["closure_item_count"] == 2
    assert payload["latest_report_summary"]["closure_item_count"] == 2
    assert payload["latest_report_summary"]["evidence_readiness_summary"]["local_evidence_available_count"] == 1
    assert payload["latest_report_summary"]["evidence_readiness_summary"]["runbook_only_count"] == 1
    assert payload["latest_report_summary"]["evidence_readiness_summary"]["auto_approved"] is False
    assert payload["totals"]["review_ready_count"] == 1
    assert payload["totals"]["evidence_missing_count"] == 1
    assert payload["reports"][0]["closure_state_counts"] == {"review_ready": 1, "evidence_missing": 1}
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False


def test_closure_evidence_index_tracks_latest_report_separately_from_historical_totals(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    older = source / "2026_older_launch_blocker_closure_workflow.json"
    newer = source / "2026_newer_launch_blocker_closure_workflow.json"
    _write_json(
        older,
        _closure_report(
            generated_at="2026-06-04T20:00:00+00:00",
            closure_item_count=50,
            review_ready_count=10,
            evidence_missing_count=20,
        ),
    )
    _write_json(
        newer,
        _closure_report(
            generated_at="2026-06-04T20:30:00+00:00",
            closure_item_count=13,
            review_ready_count=0,
            evidence_missing_count=0,
            evidence_incomplete_count=13,
        ),
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert payload["totals"]["closure_item_count"] == 63
    assert payload["latest_report"].endswith("2026_newer_launch_blocker_closure_workflow.json")
    assert payload["latest_report_summary"]["closure_item_count"] == 13
    assert payload["latest_report_summary"]["evidence_incomplete_count"] == 13


def test_closure_evidence_index_blocks_secret_like_report_without_leak(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    key_value = "sk-" + "index-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        source / "2026_demo_launch_blocker_closure_workflow.json",
        {
            **_closure_report(),
            "api_key": key_value,
            "DATABASE_URL": db_url,
        },
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["report_count"] == 0
    assert any("secret_like_value_detected" in item for item in payload["warnings"])
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_closure_evidence_index_blocks_auto_close_or_non_read_only_reports(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    _write_json(
        source / "2026_demo_launch_blocker_closure_workflow.json",
        _closure_report(read_only=False, auto_approved=True, auto_closed=True),
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["reports"][0]["read_only"] is False
    assert payload["reports"][0]["auto_approved"] is True
    assert payload["reports"][0]["auto_closed"] is True
    assert payload["go_no_go"]["recommendation"] == "No-Go"


def test_closure_evidence_index_blocks_unexpected_execution_flags(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    _write_json(
        source / "2026_demo_launch_blocker_closure_workflow.json",
        _closure_report(deployment_executed=True, release_created=True, tag_created=True),
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert set(payload["reports"][0]["unexpected_execution_flags"]) == {
        "deployment_executed",
        "release_created",
        "tag_created",
    }
    assert payload["go_no_go"]["recommendation"] == "No-Go"


def test_closure_evidence_index_sanitizes_secret_like_paths(tmp_path: Path) -> None:
    source = tmp_path / ("token=secret-dir") / "closure"
    _write_json(
        source / "sk-path-secret_launch_blocker_closure_workflow.json",
        _closure_report(),
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "partial"
    assert "token=secret-dir" not in merged
    assert "sk-path-secret" not in merged
    assert "[REDACTED]" in merged


def test_closure_evidence_index_ignores_markdown_body(tmp_path: Path) -> None:
    source = tmp_path / "closure"
    _write_json(source / "2026_demo_launch_blocker_closure_workflow.json", _closure_report())
    (source / "2026_demo_launch_blocker_closure_workflow.md").write_text(
        "api_key=sk-markdown-body-should-not-be-read",
        encoding="utf-8",
    )

    summary = build_closure_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "partial"
    assert "sk-markdown-body-should-not-be-read" not in merged
