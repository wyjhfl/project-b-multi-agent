from __future__ import annotations

import json
from pathlib import Path

from scripts import manual_signoff_package as module
from scripts.manual_signoff_package import build_manual_signoff_package, build_signoff_record_template


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _index_payload(**overrides: object) -> dict:
    payload = {
        "status": "partial",
        "version": "4.1.0-planning",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "auto_approved": False,
        "auto_closed": False,
        "report_count": 1,
        "latest_report": "docs/reports/launch_blocker_closure/demo.json",
        "totals": {
            "closure_item_count": 2,
            "review_ready_count": 1,
            "evidence_missing_count": 1,
            "evidence_incomplete_count": 0,
            "blocked_closure_count": 0,
        },
    }
    payload.update(overrides)
    return payload


def test_manual_signoff_package_skips_without_input(tmp_path: Path) -> None:
    summary = build_manual_signoff_package(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["manual_signoff_required"] is True
    assert payload["manual_signoff_completed"] is False
    assert payload["auto_signed"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"
    assert "closure_index:input_not_provided" in payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_manual_signoff_package_cli_uses_latest_index_and_default_record(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "manual"
    closure_index_dir = tmp_path / "closure_index"
    closure_index_dir.mkdir(parents=True)
    signoff_record = output_dir / "manual_signoff_record.template.json"
    output_dir.mkdir(parents=True)
    _write_json(closure_index_dir / "001_closure_evidence_index.json", _index_payload())
    _write_json(
        signoff_record,
        {
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [
                {"role": "release_manager", "name": "", "approved": False},
                {"role": "security_reviewer", "name": "", "approved": False},
                {"role": "business_owner", "name": "", "approved": False},
                {"role": "operations_owner", "name": "", "approved": False},
            ],
        },
    )
    monkeypatch.setattr(module, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(module, "DEFAULT_CLOSURE_INDEX_DIR", closure_index_dir)
    monkeypatch.setattr(module, "DEFAULT_SIGNOFF_RECORD", signoff_record)
    monkeypatch.setattr("sys.argv", ["manual_signoff_package.py"])

    assert module.main() == 0
    summary = json.loads(capsys.readouterr().out)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["closure_index_source"]["loaded"] is True
    assert payload["manual_signoff_record_source"]["loaded"] is True
    assert "closure_index:input_not_provided" not in payload["missing_conditions"]
    assert "manual_signoff_record:input_not_provided" not in payload["missing_conditions"]


def test_manual_signoff_package_cli_prefers_filled_record_over_template(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "manual"
    closure_index_dir = tmp_path / "closure_index"
    closure_index_dir.mkdir(parents=True)
    template_record = output_dir / "manual_signoff_record.template.json"
    filled_record = output_dir / "manual_signoff_record.json"
    output_dir.mkdir(parents=True)
    _write_json(closure_index_dir / "001_closure_evidence_index.json", _index_payload())
    _write_json(template_record, {"manual_signoff_completed": False, "decision": "No-Go"})
    _write_json(
        filled_record,
        {
            "manual_signoff_completed": True,
            "decision": "Go",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [
                {"role": "release_manager", "name": "release", "approved": True},
                {"role": "security_reviewer", "name": "security", "approved": True},
                {"role": "business_owner", "name": "business", "approved": True},
                {"role": "operations_owner", "name": "ops", "approved": True},
            ],
            "evidence_acknowledgements": [
                {"item": "real_llm_preflight", "accepted": True},
                {"item": "postgres_redis_mcp_smoke", "accepted": True},
                {"item": "business_read_smoke", "accepted": True},
                {"item": "closure_evidence_review", "accepted": True},
            ],
        },
    )
    monkeypatch.setattr(module, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(module, "DEFAULT_CLOSURE_INDEX_DIR", closure_index_dir)
    monkeypatch.setattr(module, "DEFAULT_SIGNOFF_RECORD", template_record)
    monkeypatch.setattr(module, "DEFAULT_FILLED_SIGNOFF_RECORD", filled_record)
    monkeypatch.setattr(module, "DEFAULT_DRAFT_SIGNOFF_RECORD", output_dir / "manual_signoff_record.draft.json")
    monkeypatch.setattr("sys.argv", ["manual_signoff_package.py"])

    assert module.main() == 0
    summary = json.loads(capsys.readouterr().out)
    payload = _read_payload(summary)

    assert payload["manual_signoff_record_source"]["path"] == str(filled_record)
    assert payload["manual_signoff_completed"] is True


def test_manual_signoff_package_cli_prefers_latest_index_generated_at(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "manual"
    closure_index_dir = tmp_path / "closure_index"
    closure_index_dir.mkdir(parents=True)
    signoff_record = output_dir / "manual_signoff_record.template.json"
    output_dir.mkdir(parents=True)
    _write_json(
        closure_index_dir / "999_closure_evidence_index.json",
        _index_payload(
            generated_at="2026-06-04T20:00:00+00:00",
            latest_report_summary={"closure_item_count": 1, "evidence_readiness_summary": {"missing_count": 1}},
        ),
    )
    _write_json(
        closure_index_dir / "001_closure_evidence_index.json",
        _index_payload(
            generated_at="2026-06-04T20:30:00+00:00",
            latest_report_summary={
                "closure_item_count": 13,
                "evidence_readiness_summary": {
                    "local_evidence_available_count": 12,
                    "runbook_only_count": 1,
                    "missing_count": 0,
                    "manual_review_required": True,
                    "auto_approved": False,
                    "auto_closed": False,
                },
            },
        ),
    )
    _write_json(
        signoff_record,
        {
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [
                {"role": "release_manager", "name": "", "approved": False},
                {"role": "security_reviewer", "name": "", "approved": False},
                {"role": "business_owner", "name": "", "approved": False},
                {"role": "operations_owner", "name": "", "approved": False},
            ],
        },
    )
    monkeypatch.setattr(module, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(module, "DEFAULT_CLOSURE_INDEX_DIR", closure_index_dir)
    monkeypatch.setattr(module, "DEFAULT_SIGNOFF_RECORD", signoff_record)
    monkeypatch.setattr("sys.argv", ["manual_signoff_package.py"])

    assert module.main() == 0
    summary = json.loads(capsys.readouterr().out)
    payload = _read_payload(summary)
    readiness = payload["signoff_sections"][0]["evidence_readiness_summary"]

    assert payload["signoff_sections"][0]["closure_item_count"] == 13
    assert readiness["local_evidence_available_count"] == 12
    assert readiness["runbook_only_count"] == 1
    assert readiness["missing_count"] == 0


def test_manual_signoff_record_template_is_not_preapproved(tmp_path: Path) -> None:
    template = tmp_path / "signoff_template.json"

    summary = build_signoff_record_template(output_path=template)
    payload = json.loads(template.read_text(encoding="utf-8"))

    assert summary["status"] == "success"
    assert payload["manual_signoff_completed"] is False
    assert payload["decision"] == "No-Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["auto_signed"] is False
    assert payload["auto_approved"] is False
    assert {item["approved"] for item in payload["roles"]} == {False}
    assert {item["accepted"] for item in payload["evidence_acknowledgements"]} == {False}
    assert {item["item"] for item in payload["evidence_acknowledgements"]} == {
        "real_llm_preflight",
        "postgres_redis_mcp_smoke",
        "business_read_smoke",
        "closure_evidence_review",
    }
    assert all("latest_report" in item for item in payload["evidence_acknowledgements"])
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "确认发布窗口" in rendered
    assert "确认 OpenAI-compatible 真实 LLM 预检报告为 success" in rendered
    assert "填写真实签核人姓名或工号" in rendered
    assert "纭" not in rendered
    assert "鍙" not in rendered


def test_manual_signoff_package_runbook_documents_evidence_acknowledgements() -> None:
    text = Path("docs/manual_signoff_package_v41.md").read_text(encoding="utf-8")

    assert "人工签核包" in text
    assert "OpenAI-compatible 真实 LLM 预检报告" in text
    assert "小米真实 LLM" not in text
    assert "real_llm_preflight" in text
    assert "postgres_redis_mcp_smoke" in text
    assert "business_read_smoke" in text
    assert "closure_evidence_review" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "鐢" not in text
    assert "鍙" not in text


def test_manual_signoff_package_builds_manual_review_package(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload())

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["manual_signoff_completed"] is False
    assert {item["auto_signed"] for item in payload["signoff_sections"]} == {False}
    summary_section = payload["signoff_sections"][0]
    assert summary_section["closure_item_count"] == 2
    assert summary_section["manual_signoff_required"] is True
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_manual_signoff_package_prefers_latest_report_summary_over_historical_totals(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(
        index,
        _index_payload(
            latest_report_summary={
                "closure_item_count": 13,
                "review_ready_count": 0,
                "evidence_missing_count": 0,
                "evidence_incomplete_count": 13,
                "blocked_closure_count": 0,
                "evidence_readiness_summary": {
                    "local_evidence_available_count": 12,
                    "runbook_only_count": 1,
                    "missing_count": 0,
                    "manual_review_required": True,
                    "auto_approved": False,
                    "auto_closed": False,
                },
            },
            totals={
                "closure_item_count": 52,
                "review_ready_count": 0,
                "evidence_missing_count": 13,
                "evidence_incomplete_count": 39,
                "blocked_closure_count": 0,
            },
        ),
    )

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)
    summary_section = payload["signoff_sections"][0]

    assert summary["status"] == "partial"
    assert summary_section["closure_item_count"] == 13
    assert summary_section["evidence_missing_count"] == 0
    assert summary_section["evidence_incomplete_count"] == 13
    assert summary_section["evidence_readiness_summary"]["local_evidence_available_count"] == 12
    assert summary_section["evidence_readiness_summary"]["runbook_only_count"] == 1
    assert summary_section["evidence_readiness_summary"]["missing_count"] == 0
    assert summary_section["evidence_readiness_summary"]["auto_approved"] is False


def test_manual_signoff_package_accepts_complete_manual_record(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    record = tmp_path / "signoff.json"
    _write_json(index, _index_payload())
    _write_json(
        record,
        {
            "manual_signoff_completed": True,
            "decision": "Go",
            "signed_at": "2026-06-04T14:10:00+00:00",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [
                {"role": "release_manager", "name": "release", "approved": True},
                {"role": "security_reviewer", "name": "security", "approved": True},
                {"role": "business_owner", "name": "business", "approved": True},
                {"role": "operations_owner", "name": "ops", "approved": True},
            ],
            "evidence_acknowledgements": [
                {"item": "real_llm_preflight", "accepted": True},
                {"item": "postgres_redis_mcp_smoke", "accepted": True},
                {"item": "business_read_smoke", "accepted": True},
                {"item": "closure_evidence_review", "accepted": True},
            ],
        },
    )

    summary = build_manual_signoff_package(
        output_dir=tmp_path / "out",
        closure_index=index,
        signoff_record=record,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert summary["manual_signoff_completed"] is True
    assert payload["manual_signoff_record_present"] is True
    assert payload["manual_signoff_decision"] == "Go"
    assert set(payload["manual_signoff_roles"]) == {
        "release_manager",
        "security_reviewer",
        "business_owner",
        "operations_owner",
    }
    assert payload["manual_signoff_blockers"] == []
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_manual_signoff_package_requires_evidence_acknowledgements(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    record = tmp_path / "signoff.json"
    _write_json(index, _index_payload())
    _write_json(
        record,
        {
            "manual_signoff_completed": True,
            "decision": "Go",
            "signed_at": "2026-06-04T14:10:00+00:00",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [
                {"role": "release_manager", "name": "release", "approved": True},
                {"role": "security_reviewer", "name": "security", "approved": True},
                {"role": "business_owner", "name": "business", "approved": True},
                {"role": "operations_owner", "name": "ops", "approved": True},
            ],
            "evidence_acknowledgements": [
                {"item": "real_llm_preflight", "accepted": True},
            ],
        },
    )

    summary = build_manual_signoff_package(
        output_dir=tmp_path / "out",
        closure_index=index,
        signoff_record=record,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert summary["manual_signoff_completed"] is False
    assert "manual_signoff_record:evidence_ack_postgres_redis_mcp_smoke_not_accepted" in payload["missing_conditions"]
    assert "manual_signoff_record:evidence_ack_business_read_smoke_not_accepted" in payload["missing_conditions"]
    assert "manual_signoff_record:evidence_ack_closure_evidence_review_not_accepted" in payload["missing_conditions"]


def test_manual_signoff_package_keeps_incomplete_record_partial(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    record = tmp_path / "signoff.json"
    _write_json(index, _index_payload())
    _write_json(
        record,
        {
            "manual_signoff_completed": True,
            "decision": "Go",
            "public_production_direct_launch": "No-Go",
            "roles": [
                {"role": "release_manager", "name": "release", "approved": True},
            ],
        },
    )

    summary = build_manual_signoff_package(
        output_dir=tmp_path / "out",
        closure_index=index,
        signoff_record=record,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert summary["manual_signoff_completed"] is False
    assert "manual_signoff_record:security_reviewer_missing" in payload["missing_conditions"]
    assert "manual_signoff_record:business_owner_missing" in payload["missing_conditions"]
    assert "manual_signoff_record:operations_owner_missing" in payload["missing_conditions"]


def test_manual_signoff_package_preserves_loaded_skipped_source(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload(status="skipped"))

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["closure_index_source"]["loaded"] is True
    assert payload["closure_index_source"]["status"] == "skipped"
    assert "closure_index:source_status_skipped" in payload["missing_conditions"]
    assert payload["go_no_go"]["production_direct_launch"] == "No-Go"


def test_manual_signoff_package_blocks_source_blocked(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload(status="blocked"))

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["go_no_go"]["recommendation"] == "No-Go"
    assert "closure_index:source_status_blocked" in payload["missing_conditions"]


def test_manual_signoff_package_blocks_secret_like_input_without_leak(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    key_value = "sk-" + "signoff-secret"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(index, _index_payload(api_key=key_value, DATABASE_URL=db_url))

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "closure_index:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_manual_signoff_package_blocks_unexpected_auto_flags(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write_json(index, _index_payload(read_only=False, auto_approved=True, auto_closed=True, release_created=True))

    summary = build_manual_signoff_package(output_dir=tmp_path / "out", closure_index=index)
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["release_created"] is False
    assert "closure_index:not_read_only" in payload["missing_conditions"]
    assert "closure_index:auto_approved_unexpected" in payload["missing_conditions"]
    assert "closure_index:auto_closed_unexpected" in payload["missing_conditions"]
