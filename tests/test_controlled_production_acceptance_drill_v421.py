from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_production_acceptance_drill import (
    ACCEPTANCE_DOMAINS,
    build_controlled_production_acceptance_drill,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _evidence_payload(**overrides: object) -> dict:
    payload = {
        "status": "partial",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "acceptance_items": [
            {
                "domain": domain,
                "status": "partial",
                "evidence_refs": [f"docs/reports/redacted/{domain}.json"],
                "reviewer": "acceptance-reviewer",
                "approval_state": "pending_review",
                "read_only": True,
            }
            for domain in ACCEPTANCE_DOMAINS
        ],
    }
    payload.update(overrides)
    return payload


def test_controlled_production_acceptance_drill_skips_without_input(tmp_path: Path) -> None:
    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "4.2.0-planning"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["business_system_connected"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "acceptance_evidence:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_controlled_production_acceptance_drill_generates_manual_review_package(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    _write_json(evidence, _evidence_payload())

    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out", acceptance_evidence=evidence)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["domain_count"] == len(ACCEPTANCE_DOMAINS)
    assert payload["review_ready_domain_count"] == len(ACCEPTANCE_DOMAINS)
    assert {item["manual_review_required"] for item in payload["acceptance_domains"]} == {True}
    assert {item["auto_approved"] for item in payload["acceptance_domains"]} == {False}
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_controlled_production_acceptance_drill_missing_domain_evidence_stays_partial(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    payload = _evidence_payload()
    payload["acceptance_items"] = payload["acceptance_items"][:2]
    _write_json(evidence, payload)

    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out", acceptance_evidence=evidence)
    report = _read_payload(summary)

    assert summary["status"] == "partial"
    assert "external_mcp:acceptance_evidence_missing" in report["missing_conditions"]
    assert "release_rollback_gate:acceptance_evidence_missing" in report["missing_conditions"]


def test_controlled_production_acceptance_drill_blocks_secret_like_input_without_leak(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    key_value = "sk-" + "acceptance-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(evidence, _evidence_payload(api_key=key_value, DATABASE_URL=db_url))

    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out", acceptance_evidence=evidence)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "acceptance_evidence:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_controlled_production_acceptance_drill_blocks_real_execution_flags(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    _write_json(
        evidence,
        _evidence_payload(
            read_only=False,
            real_llm_executed=True,
            external_mcp_connected=True,
            database_connected=True,
            redis_connected=True,
            business_system_connected=True,
            deployment_executed=True,
            release_created=True,
            tag_created=True,
            auto_approved=True,
            auto_closed=True,
        ),
    )

    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out", acceptance_evidence=evidence)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["business_system_connected"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert "acceptance_evidence:not_read_only" in payload["missing_conditions"]
    assert "acceptance_evidence:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "acceptance_evidence:business_system_connected_unexpected" in payload["missing_conditions"]
    assert payload["go_no_go"]["recommendation"] == "No-Go"


def test_controlled_production_acceptance_drill_preserves_loaded_skipped_source(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    _write_json(evidence, _evidence_payload(status="skipped"))

    summary = build_controlled_production_acceptance_drill(output_dir=tmp_path / "out", acceptance_evidence=evidence)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["acceptance_evidence_source"]["loaded"] is True
    assert payload["acceptance_evidence_source"]["status"] == "skipped"
    assert "acceptance_evidence:source_status_skipped" in payload["missing_conditions"]
