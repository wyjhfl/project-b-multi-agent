from __future__ import annotations

import json
from pathlib import Path

from scripts import production_pilot_evidence_bundle as bundle
from scripts.production_pilot_evidence_bundle import build_production_pilot_evidence_bundle


def _write_json(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _patch_sources(monkeypatch, root: Path) -> dict[str, Path]:
    mapping = {
        "production_landing_final_verification": root / "final",
        "production_landing_signoff_closeout": root / "closeout",
        "production_landing_status": root / "status",
        "real_production_environment_checklist": root / "checklist",
        "real_integration_gap_register": root / "gap",
        "production_landing_text_quality": root / "quality",
    }
    monkeypatch.setattr(
        bundle,
        "REPORT_SOURCES",
        {
            source_id: (directory, f"*_{source_id}.json")
            for source_id, directory in mapping.items()
        },
    )
    return mapping


def _write_ready_sources(dirs: dict[str, Path]) -> None:
    _write_json(
        dirs["production_landing_final_verification"],
        "001_production_landing_final_verification.json",
        {
            "status": "success",
            "passed_count": 9,
            "requirement_count": 9,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["production_landing_signoff_closeout"],
        "001_production_landing_signoff_closeout.json",
        {
            "status": "success",
            "final_status": "success",
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["production_landing_status"],
        "001_production_landing_status.json",
        {
            "status": "success",
            "controlled_pilot_ready": True,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["real_production_environment_checklist"],
        "001_real_production_environment_checklist.json",
        {
            "status": "partial",
            "domain_count": 4,
            "secret_plaintext_output": False,
            "go_no_go": {"public_production_direct_launch": "No-Go"},
        },
    )
    _write_json(
        dirs["real_integration_gap_register"],
        "001_real_integration_gap_register.json",
        {
            "status": "partial",
            "gap_count": 0,
            "open_gap_count": 0,
            "secret_plaintext_output": False,
            "go_no_go": {"public_production_direct_launch": "No-Go"},
        },
    )
    _write_json(
        dirs["production_landing_text_quality"],
        "001_production_landing_text_quality.json",
        {
            "status": "success",
            "blocked_file_count": 0,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )


def test_production_pilot_evidence_bundle_success_when_closeout_and_final_verification_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_sources(dirs)

    summary = build_production_pilot_evidence_bundle(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["controlled_pilot_ready"] is True
    assert payload["final_verification_passed_count"] == 9
    assert payload["final_verification_requirement_count"] == 9
    assert payload["missing_conditions"] == []
    assert payload["go_no_go"]["controlled_pilot"] == "Go"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False


def test_production_pilot_evidence_bundle_partial_when_final_verification_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_sources(dirs)
    for item in dirs["production_landing_final_verification"].glob("*.json"):
        item.unlink()

    summary = build_production_pilot_evidence_bundle(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert "production_landing_final_verification:not_success" in payload["missing_conditions"]
    assert payload["go_no_go"]["controlled_pilot"] == "Manual-Review"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_production_pilot_evidence_bundle_blocks_secret_like_source_without_leak(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_sources(dirs)
    _write_json(
        dirs["production_landing_status"],
        "002_production_landing_status.json",
        {
            "generated_at": "2026-06-05T07:00:00+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "note": "token=sk-should-not-leak",
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_production_pilot_evidence_bundle(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert "production_pilot_evidence_bundle:secret_like_output_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged
    assert payload["go_no_go"]["controlled_pilot"] == "No-Go"


def test_production_pilot_evidence_bundle_rejects_public_direct_launch_change(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_sources(dirs)
    _write_json(
        dirs["real_integration_gap_register"],
        "002_real_integration_gap_register.json",
        {
            "generated_at": "2026-06-05T07:00:00+00:00",
            "status": "partial",
            "gap_count": 0,
            "open_gap_count": 0,
            "secret_plaintext_output": False,
            "go_no_go": {"public_production_direct_launch": "Go"},
        },
    )

    summary = build_production_pilot_evidence_bundle(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert "real_integration_gap_register:public_production_direct_launch_not_no_go" in payload[
        "missing_conditions"
    ]
    assert payload["public_production_direct_launch"] == "No-Go"
