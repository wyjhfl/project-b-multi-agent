from __future__ import annotations

import json
from pathlib import Path

from scripts.production_acceptance_gap_register import build_production_acceptance_gap_register


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _index_payload(**overrides: object) -> dict:
    payload = {
        "status": "partial",
        "version": "4.2.0-planning",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "database_connected": False,
        "redis_connected": False,
        "business_system_connected": False,
        "auto_approved": False,
        "auto_closed": False,
        "reports": [
            {
                "path": "docs/reports/controlled_production_acceptance/demo.json",
                "status": "partial",
                "domain_status_counts": {"partial": 2, "skipped": 3, "blocked": 1},
                "unexpected_execution_flags": [],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_production_acceptance_gap_register_skips_without_input(tmp_path: Path) -> None:
    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["gap_register"] == []
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "acceptance_index:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_production_acceptance_gap_register_builds_open_gaps_from_index(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload())

    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out", acceptance_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["open_gap_count"] == payload["gap_count"]
    assert {"domain_status:blocked", "domain_status:skipped"} == {
        item["source_key"] for item in payload["gap_register"]
    }
    assert {item["owner"] for item in payload["gap_register"]} == {"manual_owner_required"}
    assert {item["due_at"] for item in payload["gap_register"]} == {"manual_due_date_required"}
    assert {item["approval_state"] for item in payload["gap_register"]} == {"not_approved"}
    assert {item["status"] for item in payload["gap_register"]} == {"open"}
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"


def test_production_acceptance_gap_register_preserves_loaded_skipped_source(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload(status="skipped", reports=[]))

    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out", acceptance_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["acceptance_index_source"]["loaded"] is True
    assert {item["status"] for item in payload["gap_register"]} == {"skipped"}
    assert "acceptance_index:source_status_skipped" in payload["missing_conditions"]


def test_production_acceptance_gap_register_blocks_upstream_blocked(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload(status="blocked"))

    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out", acceptance_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "acceptance_index:source_status_blocked" in payload["missing_conditions"]
    assert {item["status"] for item in payload["gap_register"]} == {"blocked"}


def test_production_acceptance_gap_register_blocks_secret_like_input_without_leak(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    key_value = "sk-" + "gap-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(index, _index_payload(api_key=key_value, DATABASE_URL=db_url))

    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out", acceptance_index=index)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "acceptance_index:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_production_acceptance_gap_register_blocks_unexpected_flags(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(
        index,
        _index_payload(
            reports=[
                {
                    "path": "docs/reports/controlled_production_acceptance/demo.json",
                    "status": "partial",
                    "domain_status_counts": {"partial": 1},
                    "unexpected_execution_flags": ["release_created", "tag_created"],
                }
            ]
        ),
    )

    summary = build_production_acceptance_gap_register(output_dir=tmp_path / "out", acceptance_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert "acceptance_index:report_unexpected_flag:release_created" in payload["missing_conditions"]
    assert "acceptance_index:report_unexpected_flag:tag_created" in payload["missing_conditions"]
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
