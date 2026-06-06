from __future__ import annotations

import json
from pathlib import Path

import scripts.manual_signoff_record_validator as validator_module
from scripts.manual_signoff_record_validator import build_manual_signoff_record_validation


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _ack_status(**overrides: object) -> dict:
    payload = {
        "status": "success",
        "recommended_accept_count": 4,
        "item_count": 4,
        "blocked_item_count": 0,
        "secret_plaintext_output": False,
    }
    payload.update(overrides)
    return payload


def _complete_record(**overrides: object) -> dict:
    payload = {
        "manual_signoff_completed": True,
        "decision": "Go",
        "signed_at": "2026-06-04T14:10:00+00:00",
        "public_production_direct_launch": "No-Go",
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
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
    }
    payload.update(overrides)
    return payload


def test_manual_signoff_record_validator_reports_template_as_partial(tmp_path: Path) -> None:
    record = tmp_path / "manual_signoff.json"
    ack = tmp_path / "ack.json"
    _write_json(
        record,
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
            "evidence_acknowledgements": [
                {"item": "real_llm_preflight", "accepted": False},
                {"item": "postgres_redis_mcp_smoke", "accepted": False},
                {"item": "business_read_smoke", "accepted": False},
                {"item": "closure_evidence_review", "accepted": False},
            ],
        },
    )
    _write_json(ack, _ack_status(status="partial", recommended_accept_count=3))

    summary = build_manual_signoff_record_validation(signoff_record=record, ack_status_report=ack, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["manual_signoff_completed"] is False
    assert "manual_signoff_record:not_completed" in payload["missing_conditions"]
    assert "manual_signoff_record:decision_not_go" in payload["missing_conditions"]
    assert "manual_signoff_evidence_ack_status:not_all_recommended_accept" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_manual_signoff_record_validator_accepts_complete_record(tmp_path: Path) -> None:
    record = tmp_path / "manual_signoff.json"
    ack = tmp_path / "ack.json"
    _write_json(record, _complete_record())
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_validation(signoff_record=record, ack_status_report=ack, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["missing_conditions"] == []
    assert payload["manual_signoff_completed"] is True
    assert {item["approved"] for item in payload["roles"]} == {True}
    assert all("responsibility" not in item for item in payload["roles"])
    assert {item["accepted"] for item in payload["evidence_acknowledgements"]} == {True}


def test_manual_signoff_record_validator_prefers_filled_record_over_template(
    tmp_path: Path, monkeypatch
) -> None:
    record_dir = tmp_path / "manual_signoff_package"
    template = record_dir / "manual_signoff_record.template.json"
    filled = record_dir / "manual_signoff_record.json"
    ack = tmp_path / "ack.json"
    _write_json(
        template,
        {
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "roles": [],
            "evidence_acknowledgements": [],
        },
    )
    _write_json(filled, _complete_record())
    _write_json(ack, _ack_status())
    monkeypatch.setattr(validator_module, "DEFAULT_SIGNOFF_RECORD", template)
    monkeypatch.setattr(validator_module, "DEFAULT_FILLED_SIGNOFF_RECORD", filled)
    monkeypatch.setattr(validator_module, "DEFAULT_DRAFT_SIGNOFF_RECORD", record_dir / "manual_signoff_record.draft.json")

    summary = build_manual_signoff_record_validation(ack_status_report=ack, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["signoff_record_path"] == str(filled)
    assert payload["manual_signoff_completed"] is True


def test_manual_signoff_record_validator_blocks_direct_launch_change(tmp_path: Path) -> None:
    record = tmp_path / "manual_signoff.json"
    ack = tmp_path / "ack.json"
    _write_json(record, _complete_record(public_production_direct_launch="Go"))
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_validation(signoff_record=record, ack_status_report=ack, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert "manual_signoff_record:public_production_direct_launch_must_remain_no_go" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_manual_signoff_record_validator_blocks_secret_like_values(tmp_path: Path) -> None:
    record = tmp_path / "manual_signoff.json"
    ack = tmp_path / "ack.json"
    _write_json(record, _complete_record(notes=["token=sk-should-not-leak"]))
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_validation(signoff_record=record, ack_status_report=ack, output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert "manual_signoff_record_validation:secret_like_value_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in merged
