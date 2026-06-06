from __future__ import annotations

import json
from pathlib import Path

from scripts.manual_signoff_record_fill import build_manual_signoff_record_fill
from scripts.manual_signoff_record_validator import build_manual_signoff_record_validation


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _draft_payload() -> dict:
    return {
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "signed_at": "",
        "public_production_direct_launch": "No-Go",
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "roles": [
            {"role": "release_manager", "name": "", "approved": False},
            {"role": "security_reviewer", "name": "", "approved": False},
            {"role": "business_owner", "name": "", "approved": False},
            {"role": "operations_owner", "name": "", "approved": False},
        ],
        "evidence_acknowledgements": [
            {"item": "real_llm_preflight", "accepted": False, "latest_report": "llm.json", "note": "ok"},
            {"item": "postgres_redis_mcp_smoke", "accepted": False, "latest_report": "infra.json", "note": "ok"},
            {"item": "business_read_smoke", "accepted": False, "latest_report": "business.json", "note": "ok"},
            {"item": "closure_evidence_review", "accepted": False, "latest_report": "closure.json", "note": "ok"},
        ],
    }


def _ack_payload() -> dict:
    return {
        "status": "success",
        "item_count": 4,
        "recommended_accept_count": 4,
        "blocked_item_count": 0,
        "secret_plaintext_output": False,
    }


def test_manual_signoff_record_fill_requires_explicit_confirmations(tmp_path: Path) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    ack = tmp_path / "ack.json"
    _write_json(draft, _draft_payload())
    _write_json(ack, _ack_payload())

    summary = build_manual_signoff_record_fill(
        signoff_record=draft,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
        release_manager="rm",
        security_reviewer="sec",
        business_owner="biz",
        operations_owner="ops",
    )
    payload = json.loads(draft.read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["filled"] is False
    assert payload["manual_signoff_completed"] is False
    report = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert "manual_signoff_record_fill:confirm_manual_signoff_required" in report["missing_conditions"]
    assert "manual_signoff_record_fill:confirm_controlled_pilot_go_required" in report["missing_conditions"]


def test_manual_signoff_record_fill_writes_valid_go_record_without_auto_approval(tmp_path: Path) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    ack = tmp_path / "ack.json"
    _write_json(draft, _draft_payload())
    _write_json(ack, _ack_payload())

    summary = build_manual_signoff_record_fill(
        signoff_record=draft,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
        release_manager="release-owner",
        security_reviewer="security-owner",
        business_owner="business-owner",
        operations_owner="ops-owner",
        confirm_manual_signoff=True,
        confirm_controlled_pilot_go=True,
    )
    payload = json.loads(draft.read_text(encoding="utf-8"))
    validation = build_manual_signoff_record_validation(
        signoff_record=draft,
        ack_status_report=ack,
        output_dir=tmp_path / "validation",
    )

    assert summary["status"] == "success"
    assert summary["filled"] is True
    assert payload["manual_signoff_completed"] is True
    assert payload["decision"] == "Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["auto_signed"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert {item["approved"] for item in payload["roles"]} == {True}
    assert {item["accepted"] for item in payload["evidence_acknowledgements"]} == {True}
    assert validation["status"] == "success"


def test_manual_signoff_record_fill_blocks_secret_like_names(tmp_path: Path) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    ack = tmp_path / "ack.json"
    _write_json(draft, _draft_payload())
    _write_json(ack, _ack_payload())

    summary = build_manual_signoff_record_fill(
        signoff_record=draft,
        ack_status_report=ack,
        output_dir=tmp_path / "out",
        release_manager="token=sk-should-not-leak",
        security_reviewer="security-owner",
        business_owner="business-owner",
        operations_owner="ops-owner",
        confirm_manual_signoff=True,
        confirm_controlled_pilot_go=True,
    )
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["filled"] is False
    assert "sk-should-not-leak" not in merged
