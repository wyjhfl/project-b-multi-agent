from __future__ import annotations

import json
from pathlib import Path

from scripts.acceptance_drill_evidence_index import build_acceptance_drill_evidence_index


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _drill_report(**overrides: object) -> dict:
    payload = {
        "status": "partial",
        "version": "4.2.0-planning",
        "phase": "v4.2_phase_22.1",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "database_connected": False,
        "redis_connected": False,
        "business_system_connected": False,
        "auto_approved": False,
        "auto_closed": False,
        "go_no_go": {"production_direct_launch": "No-Go"},
        "domain_count": 2,
        "review_ready_domain_count": 1,
        "acceptance_domains": [
            {"domain": "real_llm", "status": "partial"},
            {"domain": "oidc_sso", "status": "skipped"},
        ],
    }
    payload.update(overrides)
    return payload


def test_acceptance_drill_index_skips_when_input_missing(tmp_path: Path) -> None:
    summary = build_acceptance_drill_evidence_index(output_dir=tmp_path / "out", input_dir=tmp_path / "missing")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["report_count"] == 0
    assert "input_dir_not_found" in payload["warnings"][0]
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert Path(summary["markdown_path"]).exists()


def test_acceptance_drill_index_indexes_reports(tmp_path: Path) -> None:
    source = tmp_path / "acceptance"
    _write_json(source / "2026_demo_controlled_production_acceptance_drill.json", _drill_report())

    summary = build_acceptance_drill_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["report_count"] == 1
    assert payload["totals"]["domain_count"] == 2
    assert payload["totals"]["review_ready_domain_count"] == 1
    assert payload["reports"][0]["domain_status_counts"] == {"partial": 1, "skipped": 1}
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False


def test_acceptance_drill_index_blocks_secret_like_report_without_leak(tmp_path: Path) -> None:
    source = tmp_path / "acceptance"
    key_value = "sk-" + "acceptance-index-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        source / "2026_demo_controlled_production_acceptance_drill.json",
        _drill_report(api_key=key_value, DATABASE_URL=db_url),
    )

    summary = build_acceptance_drill_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["report_count"] == 0
    assert any("secret_like_value_detected" in item for item in payload["warnings"])
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_acceptance_drill_index_blocks_unexpected_execution_flags(tmp_path: Path) -> None:
    source = tmp_path / "acceptance"
    _write_json(
        source / "2026_demo_controlled_production_acceptance_drill.json",
        _drill_report(real_llm_executed=True, database_connected=True, release_created=True, tag_created=True),
    )

    summary = build_acceptance_drill_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert set(payload["reports"][0]["unexpected_execution_flags"]) == {
        "real_llm_executed",
        "database_connected",
        "release_created",
        "tag_created",
    }
    assert payload["go_no_go"]["recommendation"] == "No-Go"


def test_acceptance_drill_index_sanitizes_secret_like_paths_and_ignores_markdown(tmp_path: Path) -> None:
    source = tmp_path / "token=secret-dir"
    _write_json(
        source / "sk-path-secret_controlled_production_acceptance_drill.json",
        _drill_report(),
    )
    (source / "sk-path-secret_controlled_production_acceptance_drill.md").write_text(
        "api_key=sk-markdown-body-should-not-be-read",
        encoding="utf-8",
    )

    summary = build_acceptance_drill_evidence_index(output_dir=tmp_path / "out", input_dir=source)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "partial"
    assert "token=secret-dir" not in merged
    assert "sk-path-secret" not in merged
    assert "sk-markdown-body-should-not-be-read" not in merged
    assert "[REDACTED]" in merged
