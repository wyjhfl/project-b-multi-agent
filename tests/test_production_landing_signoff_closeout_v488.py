from __future__ import annotations

import json
from pathlib import Path

import scripts.production_landing_signoff_closeout as closeout
from scripts.production_landing_signoff_closeout import build_production_landing_signoff_closeout


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


def test_signoff_closeout_requires_explicit_confirmations_and_does_not_write_target(tmp_path: Path) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    _write_json(draft, _draft_payload())

    summary = build_production_landing_signoff_closeout(
        output_dir=tmp_path / "out",
        signoff_record=draft,
        target_record=target,
        release_manager="rm",
        security_reviewer="sec",
        business_owner="biz",
        operations_owner="ops",
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["target_record_written"] is False
    assert not target.exists()
    assert "production_landing_signoff_closeout:confirm_manual_signoff_required" in payload["missing_conditions"]
    assert "production_landing_signoff_closeout:confirm_controlled_pilot_go_required" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_signoff_closeout_blocks_secret_like_role_names_without_leaking_value(tmp_path: Path) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    _write_json(draft, _draft_payload())

    summary = build_production_landing_signoff_closeout(
        output_dir=tmp_path / "out",
        signoff_record=draft,
        target_record=target,
        release_manager="token=sk-should-not-leak",
        security_reviewer="sec",
        business_owner="biz",
        operations_owner="ops",
        confirm_manual_signoff=True,
        confirm_controlled_pilot_go=True,
    )
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["target_record_written"] is False
    assert "sk-should-not-leak" not in merged


def test_signoff_closeout_runs_ordered_closeout_steps_after_explicit_signoff(tmp_path: Path, monkeypatch) -> None:
    draft = tmp_path / "manual_signoff_record.draft.json"
    target = tmp_path / "manual_signoff_record.json"
    ack = tmp_path / "ack.json"
    _write_json(draft, _draft_payload())
    _write_json(ack, _ack_payload())

    def fake_blocker() -> dict:
        return {"status": "success", "json_path": "blocker.json", "secret_plaintext_output": False}

    def fake_refresh(**_: object) -> dict:
        return {"status": "success", "json_path": "refresh.json", "secret_plaintext_output": False}

    def fake_status() -> dict:
        return {"status": "success", "json_path": "status.json", "secret_plaintext_output": False}

    def fake_final() -> dict:
        return {"status": "success", "json_path": "final.json", "secret_plaintext_output": False}

    monkeypatch.setattr(closeout, "build_production_landing_blocker_resolution", fake_blocker)
    monkeypatch.setattr(closeout, "build_production_landing_refresh_status", fake_refresh)
    monkeypatch.setattr(closeout, "build_production_landing_status", fake_status)
    monkeypatch.setattr(closeout, "build_production_landing_final_verification", fake_final)
    monkeypatch.setattr(
        "scripts.manual_signoff_record_fill.DEFAULT_ACK_STATUS_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "scripts.manual_signoff_record_promote.DEFAULT_ACK_STATUS_DIR",
        tmp_path,
    )

    summary = build_production_landing_signoff_closeout(
        output_dir=tmp_path / "out",
        signoff_record=draft,
        target_record=target,
        ack_status_report=ack,
        release_manager="rm",
        security_reviewer="sec",
        business_owner="biz",
        operations_owner="ops",
        confirm_manual_signoff=True,
        confirm_controlled_pilot_go=True,
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    target_payload = json.loads(target.read_text(encoding="utf-8"))

    assert summary["status"] == "success"
    assert summary["final_status"] == "success"
    assert summary["target_record_written"] is True
    assert target_payload["manual_signoff_completed"] is True
    assert target_payload["decision"] == "Go"
    assert target_payload["public_production_direct_launch"] == "No-Go"
    assert payload["steps"][-1]["step_id"] == "production_landing_final_verification"
    assert payload["secret_plaintext_output"] is False
