from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_evidence_freshness import build_production_landing_evidence_freshness


def _write_report(directory: Path, name: str, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_evidence_freshness_success_when_reports_match_head(tmp_path: Path) -> None:
    current_commit = "abcdef1234567890"
    status_dir = tmp_path / "status"
    final_dir = tmp_path / "final"
    _write_report(
        status_dir,
        "2026-06-06_status_production_landing_status.json",
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "commit": current_commit,
            "status": "partial",
            "secret_plaintext_output": False,
        },
    )
    _write_report(
        final_dir,
        "2026-06-06_final_production_landing_final_verification.json",
        {
            "generated_at": "2026-06-06T00:01:00+00:00",
            "commit": current_commit,
            "status": "partial",
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_evidence_freshness(
        output_dir=tmp_path / "out",
        sources={
            "production_landing_status": (status_dir, "*_production_landing_status.json"),
            "production_landing_final_verification": (final_dir, "*_production_landing_final_verification.json"),
        },
        current_commit=current_commit,
        worktree_clean=True,
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert summary["stale_source_count"] == 0
    assert payload["missing_conditions"] == []
    assert {item["commit_matches_head"] for item in payload["sources"]} == {True}
    assert payload["public_production_direct_launch"] == "No-Go"


def test_evidence_freshness_reports_partial_for_stale_or_missing_sources(tmp_path: Path) -> None:
    current_commit = "abcdef1234567890"
    status_dir = tmp_path / "status"
    missing_dir = tmp_path / "missing"
    _write_report(
        status_dir,
        "2026-06-06_status_production_landing_status.json",
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "commit": "100cdc2e9e0cc45d8c43b5384c9569f0f6b8ae38",
            "status": "partial",
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_evidence_freshness(
        output_dir=tmp_path / "out",
        sources={
            "production_landing_status": (status_dir, "*_production_landing_status.json"),
            "production_landing_final_verification": (missing_dir, "*_production_landing_final_verification.json"),
        },
        current_commit=current_commit,
        worktree_clean=False,
    )
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert summary["stale_source_count"] == 2
    assert "production_landing_status:commit_not_current_head" in payload["missing_conditions"]
    assert "production_landing_final_verification:report_not_found" in payload["missing_conditions"]
    assert "git:worktree_dirty" in payload["missing_conditions"]
    assert payload["secret_plaintext_output"] is False


def test_evidence_freshness_blocks_without_leaking_secret_like_report_payload(tmp_path: Path) -> None:
    current_commit = "abcdef1234567890"
    status_dir = tmp_path / "status"
    secret_value = "tp-abcdefghijklmnopqrstuvwxyz123456"
    _write_report(
        status_dir,
        "2026-06-06_status_production_landing_status.json",
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "commit": current_commit,
            "status": "partial",
            "debug_value": secret_value,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_evidence_freshness(
        output_dir=tmp_path / "out",
        sources={"production_landing_status": (status_dir, "*_production_landing_status.json")},
        current_commit=current_commit,
        worktree_clean=True,
    )
    payload_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert summary["status"] == "blocked"
    assert "production_landing_status:secret_like_output_detected" in payload["missing_conditions"]
    assert secret_value not in payload_text
    assert payload["sources"][0]["secret_like_detected"] is True


def test_evidence_freshness_allows_safe_secret_placeholders(tmp_path: Path) -> None:
    current_commit = "abcdef1234567890"
    status_dir = tmp_path / "status"
    _write_report(
        status_dir,
        "2026-06-06_status_production_landing_status.json",
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "commit": current_commit,
            "status": "needs_input",
            "local_env_template_lines": [
                "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
                "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
            ],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_evidence_freshness(
        output_dir=tmp_path / "out",
        sources={"production_landing_status": (status_dir, "*_production_landing_status.json")},
        current_commit=current_commit,
        worktree_clean=True,
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["sources"][0]["secret_like_detected"] is False
    assert payload["missing_conditions"] == []
