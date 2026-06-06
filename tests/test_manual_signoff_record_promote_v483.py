from __future__ import annotations

import json
from pathlib import Path

from scripts.manual_signoff_record_promote import build_manual_signoff_record_promote


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
        "signed_at": "2026-06-05T01:30:00+00:00",
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


def test_manual_signoff_record_promote_refuses_incomplete_draft(tmp_path: Path) -> None:
    source = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    ack = tmp_path / "ack.json"
    _write_json(source, _complete_record(manual_signoff_completed=False, decision="No-Go"))
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_promote(
        source_record=source,
        target_record=target,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert summary["promoted"] is False
    assert target.exists() is False
    assert "manual_signoff_record:not_completed" in payload["missing_conditions"]
    assert payload["target_record_written"] is False
    assert payload["public_production_direct_launch"] == "No-Go"


def test_manual_signoff_record_promote_writes_valid_formal_record(tmp_path: Path) -> None:
    source = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    ack = tmp_path / "ack.json"
    record = _complete_record()
    _write_json(source, record)
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_promote(
        source_record=source,
        target_record=target,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert summary["promoted"] is True
    assert json.loads(target.read_text(encoding="utf-8")) == record
    assert payload["missing_conditions"] == []
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False


def test_manual_signoff_record_promote_blocks_secret_like_values(tmp_path: Path) -> None:
    source = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    ack = tmp_path / "ack.json"
    _write_json(source, _complete_record(notes=["token=sk-should-not-leak"]))
    _write_json(ack, _ack_status())

    summary = build_manual_signoff_record_promote(
        source_record=source,
        target_record=target,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["promoted"] is False
    assert target.exists() is False
    assert "manual_signoff_record_promote:secret_like_value_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in merged
