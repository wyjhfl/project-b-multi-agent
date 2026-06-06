from __future__ import annotations

import json
from pathlib import Path

from scripts.manual_signoff_record_draft import build_manual_signoff_record_draft


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_manual_signoff_record_draft_prefills_ack_evidence_without_auto_approval(tmp_path: Path) -> None:
    ack = tmp_path / "ack.json"
    output = tmp_path / "manual_signoff_record.draft.json"
    _write_json(
        ack,
        {
            "status": "partial",
            "items": [
                {
                    "item": "real_llm_preflight",
                    "latest_report": "docs/reports/production_landing_xiaomi_llm_preflight/latest.json",
                    "source_status": "skipped",
                    "recommended_accept": False,
                    "missing_conditions": ["real_llm_preflight:status_not_success"],
                },
                {
                    "item": "business_read_smoke",
                    "latest_report": "docs/reports/business_system_read_smoke/latest.json",
                    "source_status": "success",
                    "recommended_accept": True,
                    "missing_conditions": [],
                },
            ],
            "secret_plaintext_output": False,
        },
    )

    summary = build_manual_signoff_record_draft(output_path=output, ack_status_report=ack)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary["status"] == "success"
    assert payload["manual_signoff_completed"] is False
    assert payload["decision"] == "No-Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["auto_signed"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["roles"][0]["responsibility"] == "确认发布窗口、回滚方案、变更审批和版本范围。"
    assert payload["roles"][1]["responsibility"] == "确认密钥不泄漏、权限边界、审计证据和安全复核结论。"
    assert payload["notes"][0].startswith("填写真实签核人姓名或工号")
    assert "人工复核该证据项后" in payload["evidence_acknowledgements"][0]["note"]
    assert [item["role"] for item in payload["roles"]] == [
        "release_manager",
        "security_reviewer",
        "business_owner",
        "operations_owner",
    ]
    assert {item["approved"] for item in payload["roles"]} == {False}
    assert len(payload["evidence_acknowledgements"]) == 4
    real_llm = payload["evidence_acknowledgements"][0]
    assert real_llm["item"] == "real_llm_preflight"
    assert real_llm["accepted"] is False
    assert real_llm["recommended_accept"] is False
    assert real_llm["missing_conditions"] == ["real_llm_preflight:status_not_success"]
    business = [item for item in payload["evidence_acknowledgements"] if item["item"] == "business_read_smoke"][0]
    assert business["recommended_accept"] is True
    assert business["accepted"] is False
    assert summary["secret_plaintext_output"] is False
    merged = output.read_text(encoding="utf-8")
    for marker in ("纭", "浜", "濉", "鐢", "鑽", "€", "�"):
        assert marker not in merged


def test_manual_signoff_record_draft_redacts_secret_like_ack_payload(tmp_path: Path) -> None:
    ack = tmp_path / "ack.json"
    output = tmp_path / "manual_signoff_record.draft.json"
    _write_json(
        ack,
        {
            "status": "partial",
            "items": [
                {
                    "item": "real_llm_preflight",
                    "latest_report": "token=sk-should-not-leak",
                    "source_status": "skipped",
                    "recommended_accept": False,
                    "missing_conditions": ["token=sk-should-not-leak"],
                }
            ],
            "secret_plaintext_output": False,
        },
    )

    summary = build_manual_signoff_record_draft(output_path=output, ack_status_report=ack)
    merged = json.dumps(summary, ensure_ascii=False) + output.read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "manual_signoff_record_draft:secret_like_output_detected" in summary["missing_conditions"]
    assert "sk-should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged


def test_manual_signoff_record_draft_reports_missing_ack_status(tmp_path: Path) -> None:
    output = tmp_path / "manual_signoff_record.draft.json"

    summary = build_manual_signoff_record_draft(output_path=output, ack_status_report=tmp_path / "missing.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert "manual_signoff_evidence_ack_status:not_found" in summary["missing_conditions"]
    assert payload["source_ack_status"] == "missing"
    assert payload["manual_signoff_completed"] is False
