from __future__ import annotations

import json
from pathlib import Path

from scripts.pilot_closeout_report_pack import build_pilot_closeout_report_pack


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_pilot_closeout_report_pack_missing_inputs_skipped(tmp_path: Path) -> None:
    summary = build_pilot_closeout_report_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "3.5.0"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["release_created"] is False
    assert payload["tag_created"] is False
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert "pilot_handoff:input_not_provided" in payload["missing_conditions"]
    assert "governance_exceptions:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_pilot_closeout_report_pack_success_sources_still_manual_review(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    evidence = tmp_path / "evidence.json"
    readiness = tmp_path / "readiness.json"
    scoring = tmp_path / "scoring.json"
    dry_run = tmp_path / "dry_run.json"
    exceptions = tmp_path / "exceptions.json"

    _write_json(
        handoff,
        {
            "status": "success",
            "version": "3.5.0",
            "mode": "fake_offline_default",
            "read_only": True,
            "real_llm_executed": False,
            "handoff_items": [{"status": "ready"}],
            "missing_items": [],
            "known_limitations": ["公网直上 No-Go"],
            "go_no_go": {"summary": "企业内网试点可继续；公网直上 No-Go。"},
        },
    )
    _write_json(evidence, {"status": "success", "version": "3.5.0", "read_only": True, "real_llm_executed": False, "manifest_id": "m1", "total_files": 3})
    _write_json(readiness, {"readiness_status": "ready", "version": "3.5.0", "read_only": True, "real_llm_executed": False, "integrations": [{"readiness_status": "ready"}]})
    _write_json(scoring, {"status": "success", "version": "3.5.0", "read_only": True, "real_llm_executed": False, "overall_score": 92, "risk_level": "low", "dimension_scores": [{"status": "success"}]})
    _write_json(dry_run, {"status": "success", "version": "3.5.0", "read_only": True, "real_llm_executed": False, "integrations": [{"readiness_status": "ready"}]})
    _write_json(exceptions, {"status": "success", "version": "3.5.0", "read_only": True, "real_llm_executed": False, "exception_count": 1, "auto_approved": False})

    summary = build_pilot_closeout_report_pack(
        output_dir=tmp_path / "out",
        pilot_handoff=handoff,
        evidence_archive=evidence,
        integration_readiness=readiness,
        operator_scoring=scoring,
        controlled_integration=dry_run,
        governance_exceptions=exceptions,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["auto_changed"] is False
    assert payload["evidence_summary"]["loaded_count"] == 6
    assert payload["executive_summary"]["loaded_source_count"] == 6
    assert "公网直上 No-Go" in payload["known_limitations"]
    assert payload["input_sources"][0]["metadata"]["go_no_go_summary"].startswith("企业内网试点")


def test_pilot_closeout_report_pack_preserves_skipped_and_partial_semantics(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    readiness = tmp_path / "readiness.json"
    scoring = tmp_path / "scoring.json"
    _write_json(handoff, {"status": "success", "read_only": True, "real_llm_executed": False, "known_limitations": ["真实 LLM 仅 opt-in"]})
    _write_json(readiness, {"readiness_status": "skipped", "read_only": True, "real_llm_executed": False, "skipped_reasons": ["REAL_LLM_API_KEY_ENV"]})
    _write_json(scoring, {"status": "partial", "read_only": True, "real_llm_executed": False, "missing_conditions": ["operator_scoring:evidence_skipped"]})

    summary = build_pilot_closeout_report_pack(
        output_dir=tmp_path / "out",
        pilot_handoff=handoff,
        integration_readiness=readiness,
        operator_scoring=scoring,
    )
    payload = _read_payload(summary)
    source_status = {item["name"]: item["status"] for item in payload["input_sources"]}

    assert summary["status"] == "partial"
    assert source_status["integration_readiness"] == "skipped"
    assert "integration_readiness:source_status_skipped" in payload["missing_conditions"]
    assert "REAL_LLM_API_KEY_ENV" in payload["missing_conditions"]
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert any("不得在 closeout 中覆盖为 success" in item for item in payload["next_actions"])


def test_pilot_closeout_report_pack_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    key_value = "sk-" + "should-not-leak"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        evidence,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "api_key": key_value,
            "DATABASE_URL": db_url,
            "missing_conditions": [db_url],
        },
    )

    summary = build_pilot_closeout_report_pack(output_dir=tmp_path / "out", evidence_archive=evidence)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "evidence_archive:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_pilot_closeout_report_pack_blocks_unexpected_real_execution(tmp_path: Path) -> None:
    dry_run = tmp_path / "dry_run.json"
    _write_json(
        dry_run,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": True,
            "external_mcp_connected": True,
        },
    )

    summary = build_pilot_closeout_report_pack(output_dir=tmp_path / "out", controlled_integration=dry_run)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert "controlled_integration:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "controlled_integration:external_mcp_connected_unexpected" in payload["missing_conditions"]
