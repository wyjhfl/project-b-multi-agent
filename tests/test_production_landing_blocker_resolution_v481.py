from __future__ import annotations

import json
from pathlib import Path

from scripts import production_landing_blocker_resolution as module
from scripts.production_landing_blocker_resolution import build_production_landing_blocker_resolution


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _patch_sources(monkeypatch, root: Path) -> dict[str, Path]:
    dirs = {
        "production_landing_status": root / "production_landing_status",
        "production_landing_action_pack": root / "production_landing_action_pack",
        "production_landing_final_verification": root / "production_landing_final_verification",
        "production_landing_xiaomi_llm_preflight": root / "production_landing_xiaomi_llm_preflight",
        "manual_signoff_evidence_ack_status": root / "manual_signoff_evidence_ack_status",
        "manual_signoff_record_validation": root / "manual_signoff_record_validation",
        "manual_signoff_record_promote": root / "manual_signoff_record_promote",
    }
    monkeypatch.setattr(
        module,
        "REPORT_SOURCES",
        {
            "production_landing_status": {
                "dir": dirs["production_landing_status"],
                "pattern": "*_production_landing_status.json",
            },
            "production_landing_action_pack": {
                "dir": dirs["production_landing_action_pack"],
                "pattern": "*_production_landing_action_pack.json",
            },
            "production_landing_final_verification": {
                "dir": dirs["production_landing_final_verification"],
                "pattern": "*_production_landing_final_verification.json",
            },
            "production_landing_xiaomi_llm_preflight": {
                "dir": dirs["production_landing_xiaomi_llm_preflight"],
                "pattern": "*_production_landing_xiaomi_llm_preflight.json",
            },
            "manual_signoff_evidence_ack_status": {
                "dir": dirs["manual_signoff_evidence_ack_status"],
                "pattern": "*_manual_signoff_evidence_ack_status.json",
            },
            "manual_signoff_record_validation": {
                "dir": dirs["manual_signoff_record_validation"],
                "pattern": "*_manual_signoff_record_validation.json",
            },
            "manual_signoff_record_promote": {
                "dir": dirs["manual_signoff_record_promote"],
                "pattern": "*_manual_signoff_record_promote.json",
            },
        },
    )
    return dirs


def _write_ready_reports(dirs: dict[str, Path]) -> None:
    _write_json(
        dirs["production_landing_status"] / "001_production_landing_status.json",
        {
            "status": "success",
            "xiaomi_llm": {
                "status": "success",
                "api_key_present": True,
                "network_check_executed": True,
                "real_llm_executed": True,
            },
            "manual_signoff": {"completed": True, "decision": "Go", "record_present": True},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_action_pack"] / "001_production_landing_action_pack.json",
        {
            "status": "success",
            "required_input_count": 0,
            "required_inputs": [],
            "required_env": [
                "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                "DATABASE_URL=<secret-managed-url>",
            ],
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_final_verification"] / "001_production_landing_final_verification.json",
        {"status": "success", "missing_conditions": [], "secret_plaintext_output": False},
    )
    _write_json(
        dirs["production_landing_xiaomi_llm_preflight"] / "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "success",
            "api_key_present": True,
            "real_llm_executed": True,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["manual_signoff_evidence_ack_status"] / "001_manual_signoff_evidence_ack_status.json",
        {"status": "success", "recommended_accept_count": 4, "secret_plaintext_output": False},
    )
    _write_json(
        dirs["manual_signoff_record_validation"] / "001_manual_signoff_record_validation.json",
        {"status": "success", "manual_signoff_completed": True, "secret_plaintext_output": False},
    )
    _write_json(
        dirs["manual_signoff_record_promote"] / "001_manual_signoff_record_promote.json",
        {"status": "success", "promoted": True, "secret_plaintext_output": False},
    )


def test_blocker_resolution_reports_required_actions_for_llm_and_signoff(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["production_landing_status"] / "002_production_landing_status.json",
        {
            "generated_at": "2026-06-05T00:00:00+00:00",
            "status": "partial",
            "xiaomi_llm": {
                "status": "skipped",
                "api_key_present": False,
                "network_check_requested": True,
                "network_check_allowed": False,
                "network_check_executed": False,
                "real_llm_executed": False,
                "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                "acceptance_blockers": [
                    "missing_process_env:XIAOMI_LLM_API_KEY",
                    "network_check_not_allowed_without_process_key",
                ],
            },
            "manual_signoff": {"completed": False, "decision": "No-Go", "record_present": True},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_action_pack"] / "002_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-05T00:00:00+00:00",
            "status": "partial",
            "required_input_count": 1,
            "required_inputs": [{"input_id": "manual_signoff_record", "status": "required"}],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_blocker_resolution(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["required_action_count"] == 2
    assert payload["required_actions"] == ["real_llm_preflight", "manual_signoff_record"]
    assert payload["actions"][0]["safe_commands"][0] == "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1"
    assert payload["actions"][0]["evidence"]["network_check_requested"] is True
    assert payload["actions"][0]["evidence"]["network_check_allowed"] is False
    assert (
        payload["actions"][0]["evidence"]["safe_next_action"]
        == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    )
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in payload["actions"][0]["evidence"]["acceptance_blockers"]
    signoff_action = [item for item in payload["actions"] if item["action_id"] == "manual_signoff_record"][0]
    assert "python scripts/manual_signoff_record_draft.py" in signoff_action["safe_commands"]
    assert "powershell -ExecutionPolicy Bypass -File scripts/production_landing_signoff_closeout.ps1" in signoff_action[
        "safe_commands"
    ]
    assert any("production_landing_signoff_closeout.py" in command for command in signoff_action["safe_commands"])
    assert "python scripts/manual_signoff_record_promote.py" in signoff_action["safe_commands"]
    assert signoff_action["evidence"]["promote_status"] == "success"
    assert signoff_action["evidence"]["promoted"] is True
    assert payload["secret_plaintext_output"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["source_blocked_or_failed"] == []


def test_blocker_resolution_success_when_all_actions_resolved(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)

    summary = build_production_landing_blocker_resolution(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["required_action_count"] == 0
    assert payload["required_actions"] == []
    assert {item["status"] for item in payload["actions"]} == {"resolved"}


def test_blocker_resolution_treats_final_verification_blocked_as_soft_source(
    tmp_path: Path, monkeypatch
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["production_landing_final_verification"] / "002_production_landing_final_verification.json",
        {
            "generated_at": "2026-06-05T00:01:00+00:00",
            "status": "blocked",
            "missing_conditions": ["production_landing_status:status_not_success"],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_blocker_resolution(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["source_blocked_or_failed"] == []
    assert "production_landing_final_verification" in payload["source_missing_conditions"]


def test_blocker_resolution_blocks_secret_like_report_without_leak(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["production_landing_status"] / "002_production_landing_status.json",
        {
            "generated_at": "2026-06-05T00:01:00+00:00",
            "status": "partial",
            "xiaomi_llm": {"status": "skipped", "api_key_present": False},
            "manual_signoff": {"completed": False, "decision": "token=sk-should-not-leak"},
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_blocker_resolution(output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "secret_like_output_review" in payload["required_actions"]
    assert "sk-should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged
