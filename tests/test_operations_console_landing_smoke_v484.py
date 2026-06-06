from __future__ import annotations

import json
from pathlib import Path

from scripts import operations_console_landing_smoke as module
from scripts.operations_console_landing_smoke import build_operations_console_landing_smoke


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_operations_console_landing_smoke_default_skipped(tmp_path: Path) -> None:
    summary = build_operations_console_landing_smoke(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "skipped"
    assert payload["execute"] is False
    assert "cli:--execute_not_requested" in payload["missing_conditions"]
    assert payload["real_llm_executed"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_operations_console_landing_smoke_success_with_expected_fields(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "observability": {
            "production_landing_xiaomi_llm_preflight": {
                "status": "skipped",
                "network_check_requested": True,
                "network_check_allowed": False,
                "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                "acceptance_blockers": [
                    "missing_process_env:XIAOMI_LLM_API_KEY",
                    "network_check_not_allowed_without_process_key",
                ],
            },
            "production_landing_blocker_resolution": {
                "actions": [
                    {
                        "action_id": "real_llm_preflight",
                        "evidence": {
                            "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                            "acceptance_blockers": [
                                "missing_process_env:XIAOMI_LLM_API_KEY",
                                "network_check_not_allowed_without_process_key",
                            ],
                        },
                    }
                ]
            },
            "production_pilot_evidence_bundle": {
                "status": "success",
                "controlled_pilot_ready": True,
                "controlled_pilot": "Go",
                "final_verification_passed_count": 9,
                "final_verification_requirement_count": 9,
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_status_summary": {
                "status": "ready",
                "controlled_internal_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "blocking_reports": [],
                "source_statuses": {
                    "production_pilot_bootstrap": "partial",
                    "operations_console_landing_smoke": "success",
                },
                "operations_console_smoke_execute": True,
                "runtime_smoke_passed": True,
            },
            "controlled_pilot_operator_packet": {
                "status": "ready",
                "controlled_internal_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "window_id": "controlled-pilot-2026-06-05",
                "latest_report_present": True,
                "rollback_required": True,
                "external_expansion_requires_new_manual_go_no_go": True,
                "secret_plaintext_output": False,
            },
            "controlled_pilot_launch_gate": {
                "status": "ready",
                "ready_for_controlled_pilot": True,
                "controlled_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_launch_package": {
                "status": "ready",
                "launch_package_ready": True,
                "controlled_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_window_record": {
                "status": "opened",
                "opened": True,
                "window_id": "controlled-pilot-2026-06-05",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_window_status": {
                "status": "healthy",
                "window": {
                    "opened": True,
                    "window_id": "controlled-pilot-2026-06-05",
                },
                "operations_summary": {
                    "health_status": "ok",
                    "deployment_ok": True,
                },
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
        }
    }

    def fake_text(url: str, timeout_seconds: float):
        return (
            200,
            "<html><body>Operations 受控试点总状态摘要 controlled_internal_pilot "
            "受控试点操作员交接包 public_production_direct_launch blocking_reports rollback_required "
            "source</body></html>",
            "",
        )

    def fake_json(url: str, timeout_seconds: float):
        return 200, payload, ""

    monkeypatch.setattr(module, "_http_get_text", fake_text)
    monkeypatch.setattr(module, "_http_get_json", fake_json)

    summary = build_operations_console_landing_smoke(output_dir=tmp_path / "out", execute=True)
    report = _payload(summary)

    assert summary["status"] == "success"
    assert report["checks"]["page_http_status"] == 200
    assert report["checks"]["page_contains_operations_marker"] is True
    assert report["checks"]["page_required_markers_present"] is True
    assert report["checks"]["page_missing_markers"] == []
    assert report["checks"]["summary_http_status"] == 200
    assert report["checks"]["network_check_requested"] is True
    assert report["checks"]["network_check_allowed"] is False
    assert report["checks"]["safe_next_action"] == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in report["checks"]["acceptance_blockers"]
    assert report["checks"]["blocker_action_present"] is True
    assert report["checks"]["pilot_evidence_status"] == "success"
    assert report["checks"]["pilot_evidence_controlled_pilot_ready"] is True
    assert report["checks"]["pilot_evidence_controlled_pilot"] == "Go"
    assert report["checks"]["pilot_evidence_final_verification_passed_count"] == 9
    assert report["checks"]["pilot_evidence_final_verification_requirement_count"] == 9
    assert report["checks"]["pilot_evidence_public_production_direct_launch"] == "No-Go"
    assert report["checks"]["controlled_status_status"] == "ready"
    assert report["checks"]["controlled_status_internal_pilot"] == "Go"
    assert report["checks"]["controlled_status_public_production_direct_launch"] == "No-Go"
    assert report["checks"]["controlled_status_secret_plaintext_output"] is False
    assert report["checks"]["controlled_status_blocking_report_count"] == 0
    assert report["checks"]["controlled_status_source_status_count"] == 2
    assert report["checks"]["controlled_status_operations_console_smoke_execute"] is True
    assert report["checks"]["controlled_status_runtime_smoke_passed"] is True
    assert report["checks"]["operator_packet_status"] == "ready"
    assert report["checks"]["operator_packet_internal_pilot"] == "Go"
    assert report["checks"]["operator_packet_public_production_direct_launch"] == "No-Go"
    assert report["checks"]["operator_packet_window_id"] == "controlled-pilot-2026-06-05"
    assert report["checks"]["operator_packet_latest_report_present"] is True
    assert report["checks"]["operator_packet_rollback_required"] is True
    assert report["checks"]["operator_packet_external_expansion_requires_new_manual_go_no_go"] is True
    assert report["checks"]["operator_packet_secret_plaintext_output"] is False
    assert report["checks"]["launch_gate_status"] == "ready"
    assert report["checks"]["launch_gate_ready"] is True
    assert report["checks"]["launch_gate_controlled_pilot"] == "Go"
    assert report["checks"]["launch_gate_public_production_direct_launch"] == "No-Go"
    assert report["checks"]["launch_package_status"] == "ready"
    assert report["checks"]["launch_package_ready"] is True
    assert report["checks"]["launch_package_controlled_pilot"] == "Go"
    assert report["checks"]["launch_package_public_production_direct_launch"] == "No-Go"
    assert report["checks"]["window_record_status"] == "opened"
    assert report["checks"]["window_record_opened"] is True
    assert report["checks"]["window_record_id"] == "controlled-pilot-2026-06-05"
    assert report["checks"]["window_status_status"] == "healthy"
    assert report["checks"]["window_status_opened"] is True
    assert report["checks"]["window_status_window_id"] == "controlled-pilot-2026-06-05"
    assert report["checks"]["window_status_health_status"] == "ok"
    assert report["checks"]["window_status_deployment_ok"] is True
    assert report["checks"]["window_status_public_production_direct_launch"] == "No-Go"
    assert report["missing_conditions"] == []
    assert report["secret_plaintext_output"] is False


def test_operations_console_landing_smoke_fails_when_expected_fields_missing(tmp_path: Path, monkeypatch) -> None:
    def fake_text(url: str, timeout_seconds: float):
        return 200, "<html><body>Operations</body></html>", ""

    def fake_json(url: str, timeout_seconds: float):
        return 200, {"observability": {"production_landing_xiaomi_llm_preflight": {}}}, ""

    monkeypatch.setattr(module, "_http_get_text", fake_text)
    monkeypatch.setattr(module, "_http_get_json", fake_json)

    summary = build_operations_console_landing_smoke(output_dir=tmp_path / "out", execute=True)
    report = _payload(summary)

    assert summary["status"] == "failed"
    assert "operations_summary:xiaomi_preflight_network_check_requested_missing" in report["missing_conditions"]
    assert "operations_summary:xiaomi_preflight_safe_next_action_missing" in report["missing_conditions"]
    assert "operations_summary:pilot_evidence_bundle_status_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_status_summary_status_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_operator_packet_status_missing" in report["missing_conditions"]
    assert "operations_page:controlled_pilot_status_markers_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_launch_gate_status_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_launch_package_status_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_window_record_status_missing" in report["missing_conditions"]
    assert "operations_summary:controlled_pilot_window_status_status_missing" in report["missing_conditions"]


def test_operations_console_landing_smoke_blocks_secret_like_output(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "observability": {
            "production_landing_xiaomi_llm_preflight": {
                "status": "skipped",
                "network_check_requested": True,
                "network_check_allowed": False,
                "safe_next_action": "token=sk-should-not-leak",
                "acceptance_blockers": ["token=sk-should-not-leak"],
            },
            "production_landing_blocker_resolution": {"actions": []},
            "production_pilot_evidence_bundle": {
                "status": "success",
                "controlled_pilot_ready": True,
                "controlled_pilot": "Go",
                "final_verification_passed_count": 9,
                "final_verification_requirement_count": 9,
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_status_summary": {
                "status": "ready",
                "controlled_internal_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "blocking_reports": [],
                "source_statuses": {"operations_console_landing_smoke": "success"},
                "operations_console_smoke_execute": True,
                "runtime_smoke_passed": True,
            },
            "controlled_pilot_operator_packet": {
                "status": "ready",
                "controlled_internal_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "window_id": "controlled-pilot-2026-06-05",
                "latest_report_present": True,
                "rollback_required": True,
                "external_expansion_requires_new_manual_go_no_go": True,
                "secret_plaintext_output": False,
            },
            "controlled_pilot_launch_gate": {
                "status": "ready",
                "ready_for_controlled_pilot": True,
                "controlled_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_launch_package": {
                "status": "ready",
                "launch_package_ready": True,
                "controlled_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_window_record": {
                "status": "opened",
                "opened": True,
                "window_id": "controlled-pilot-2026-06-05",
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            "controlled_pilot_window_status": {
                "status": "healthy",
                "window": {"opened": True, "window_id": "controlled-pilot-2026-06-05"},
                "operations_summary": {"health_status": "ok", "deployment_ok": True},
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
        }
    }

    monkeypatch.setattr(
        module,
        "_http_get_text",
        lambda url, timeout_seconds: (
            200,
            "Operations 受控试点总状态摘要 controlled_internal_pilot "
            "受控试点操作员交接包 public_production_direct_launch blocking_reports rollback_required source",
            "",
        ),
    )
    monkeypatch.setattr(module, "_http_get_json", lambda url, timeout_seconds: (200, payload, ""))

    summary = build_operations_console_landing_smoke(output_dir=tmp_path / "out", execute=True)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )
    report = _payload(summary)

    assert report["status"] == "success"
    assert report["secret_plaintext_output"] is False
    assert "sk-should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged
