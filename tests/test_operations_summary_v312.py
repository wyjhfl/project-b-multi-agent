from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app, reset_runtime_for_test
from app.models.schemas import AuditEvent, TaskRun, TaskStatus

client = TestClient(app)


def _write_report(base: Path, report_id: str) -> None:
    payload = {
        "report_id": report_id,
        "generated_at": "2026-05-27T00:00:00+00:00",
        "provider": "litellm",
        "model": "gpt-4o-mini",
        "scenario": "nl2sql_preview",
        "outcome": "fallback",
        "request_id": "req-op-001",
        "fallback_used": True,
        "prompt_tokens": 9,
        "completion_tokens": 3,
        "total_tokens": 12,
        "cost": 0.06,
        "detail": {
            "prompt": "raw_prompt_text",
            "api_key": "sk-secret",
            "password": "db-password",
            "database_url": "postgresql://user:dbpassword@localhost:5432/db",
            "redis_url": "redis://:redispassword@localhost:6379/0",
        },
    }
    path = base / f"2026-05-27_{report_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_operations_summary_should_return_empty_states_when_report_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("FRONTEND_PRODUCTION_BUILD_REPORT_DIR", str(tmp_path / "missing_frontend_build"))
    monkeypatch.setenv("PRODUCTION_RUNTIME_SMOKE_REPORT_DIR", str(tmp_path / "missing_runtime_smoke"))
    monkeypatch.setenv("PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR", str(tmp_path / "missing_bootstrap"))
    monkeypatch.setenv("CONTROLLED_PILOT_LAUNCH_GATE_REPORT_DIR", str(tmp_path / "missing_controlled_pilot_gate"))
    monkeypatch.setenv("CONTROLLED_PILOT_LAUNCH_PACKAGE_REPORT_DIR", str(tmp_path / "missing_controlled_pilot_package"))
    monkeypatch.setenv("CONTROLLED_PILOT_WINDOW_RECORD_REPORT_DIR", str(tmp_path / "missing_controlled_pilot_window"))
    monkeypatch.setenv("CONTROLLED_PILOT_WINDOW_STATUS_REPORT_DIR", str(tmp_path / "missing_controlled_pilot_status"))
    monkeypatch.setenv("PRODUCTION_PILOT_SIGNOFF_REPORT_DIR", str(tmp_path / "missing_signoff"))
    monkeypatch.setenv("BUSINESS_SYSTEM_READ_SMOKE_REPORT_DIR", str(tmp_path / "missing_business_read_smoke"))
    monkeypatch.setenv(
        "BUSINESS_SYSTEM_PRODUCTION_READINESS_REPORT_DIR",
        str(tmp_path / "missing_business_system_production_readiness"),
    )
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_REPORT_DIR", str(tmp_path / "missing_real_integration_smoke"))
    monkeypatch.setenv(
        "REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_REPORT_DIR",
        str(tmp_path / "missing_real_production_environment_checklist"),
    )
    monkeypatch.setenv("PRODUCTION_LANDING_INPUT_READINESS_REPORT_DIR", str(tmp_path / "missing_landing_input_readiness"))
    monkeypatch.setenv("PRODUCTION_LANDING_ENV_CHECK_REPORT_DIR", str(tmp_path / "missing_landing_env_check"))
    monkeypatch.setenv("PRODUCTION_LANDING_ENV_RUNNER_REPORT_DIR", str(tmp_path / "missing_landing_env_runner"))
    monkeypatch.setenv("PRODUCTION_LANDING_ACTION_PACK_REPORT_DIR", str(tmp_path / "missing_landing_action_pack"))
    monkeypatch.setenv(
        "PRODUCTION_LANDING_BLOCKER_RESOLUTION_REPORT_DIR",
        str(tmp_path / "missing_landing_blocker_resolution"),
    )
    monkeypatch.setenv(
        "PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR",
        str(tmp_path / "missing_landing_final_verification"),
    )
    monkeypatch.setenv(
        "MANUAL_SIGNOFF_RECORD_VALIDATION_REPORT_DIR",
        str(tmp_path / "missing_manual_signoff_record_validation"),
    )
    monkeypatch.setenv(
        "MANUAL_SIGNOFF_RECORD_PROMOTE_REPORT_DIR",
        str(tmp_path / "missing_manual_signoff_record_promote"),
    )
    monkeypatch.setenv(
        "MANUAL_SIGNOFF_RECORD_FILL_REPORT_DIR",
        str(tmp_path / "missing_manual_signoff_record_fill"),
    )
    monkeypatch.setenv(
        "PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR",
        str(tmp_path / "missing_production_landing_signoff_closeout"),
    )
    monkeypatch.setenv(
        "PRODUCTION_LANDING_PRE_SIGNOFF_GATE_REPORT_DIR",
        str(tmp_path / "missing_production_landing_pre_signoff_gate"),
    )
    monkeypatch.setenv(
        "PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_REPORT_DIR",
        str(tmp_path / "missing_production_landing_signoff_reviewer_packet"),
    )
    monkeypatch.setenv(
        "PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR",
        str(tmp_path / "missing_production_landing_text_quality"),
    )
    monkeypatch.setenv(
        "PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR",
        str(tmp_path / "missing_production_pilot_evidence_bundle"),
    )
    monkeypatch.setenv(
        "OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR",
        str(tmp_path / "missing_operations_console_landing_smoke"),
    )
    monkeypatch.setenv(
        "CONTROLLED_PILOT_CONSOLE_VERIFY_REPORT_DIR",
        str(tmp_path / "missing_controlled_pilot_console_verify"),
    )
    monkeypatch.setenv(
        "CONTROLLED_PILOT_CONSOLE_PREFLIGHT_REPORT_DIR",
        str(tmp_path / "missing_controlled_pilot_console_preflight"),
    )

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "read_only"
    assert data["observability"]["acceptance_snapshot_runbook_path"] == "docs/acceptance_snapshot_runbook_v32.md"
    assert data["observability"]["demo_artifact_runbook_path"] == "docs/demo_artifact_bundle_runbook_v32.md"
    assert data["observability"]["artifact_default_dir"] == "docs/reports/demo_artifacts"
    assert data["observability"]["snapshot_default_dir"] == "docs/reports/acceptance_snapshots"
    assert data["observability"]["v4_evidence"]["mode"] == "read_only"
    assert data["observability"]["v4_evidence"]["boundary"]["report_content_read"] is False
    assert data["observability"]["v4_evidence"]["boundary"]["real_llm_executed"] is False
    assert data["observability"]["v4_evidence"]["boundary"]["external_system_connected"] is False
    assert data["observability"]["v4_evidence"]["entries"]["production_acceptance_gaps"]["runbook_path"] == "docs/production_acceptance_gap_register_v42.md"
    assert data["observability"]["v4_evidence"]["entries"]["real_production_environment_checklist"]["runbook_path"] == "docs/v4_5_real_production_environment_landing_plan.md"
    assert data["observability"]["v4_evidence"]["entries"]["frontend_production_build"]["runbook_path"] == "scripts/frontend_production_build_check.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_runtime_smoke"]["runbook_path"] == "scripts/production_runtime_smoke.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_pilot_bootstrap"]["runbook_path"] == "scripts/production_pilot_bootstrap.py"
    assert data["observability"]["v4_evidence"]["entries"]["controlled_pilot_launch_gate"]["runbook_path"] == "scripts/controlled_pilot_launch_gate.py"
    assert data["observability"]["v4_evidence"]["entries"]["controlled_pilot_launch_package"]["runbook_path"] == "scripts/controlled_pilot_launch_package.py"
    assert data["observability"]["v4_evidence"]["entries"]["controlled_pilot_window_record"]["runbook_path"] == "scripts/controlled_pilot_window_record.py"
    assert data["observability"]["v4_evidence"]["entries"]["controlled_pilot_window_status"]["runbook_path"] == "scripts/controlled_pilot_window_status_snapshot.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_pilot_signoff"]["runbook_path"] == "scripts/production_pilot_signoff_summary.py"
    assert data["observability"]["v4_evidence"]["entries"]["business_system_read_smoke"]["runbook_path"] == "scripts/business_system_read_smoke.py"
    assert (
        data["observability"]["v4_evidence"]["entries"]["business_system_production_readiness"]["runbook_path"]
        == "scripts/business_system_production_readiness_brief.py"
    )
    assert data["observability"]["v4_evidence"]["entries"]["real_integration_staging_smoke"]["runbook_path"] == "scripts/real_integration_staging_smoke.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_landing_input_readiness"]["runbook_path"] == "scripts/production_landing_input_readiness.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_landing_env_check"]["runbook_path"] == "scripts/production_landing_env_check.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_landing_env_runner"]["runbook_path"] == "scripts/production_landing_env_runner.py"
    assert data["observability"]["v4_evidence"]["entries"]["production_landing_action_pack"]["runbook_path"] == "scripts/production_landing_action_pack.py"
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_landing_operator_runbook"]["runbook_path"]
        == "docs/production_landing_operator_runbook_v47.md"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["xiaomi_llm_landing_resume_runbook"]["runbook_path"]
        == "docs/xiaomi_llm_landing_resume_runbook_v47.md"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["manual_signoff_record_validation"]["runbook_path"]
        == "scripts/manual_signoff_record_validator.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["manual_signoff_record_promote"]["runbook_path"]
        == "scripts/manual_signoff_record_promote.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_landing_text_quality"]["runbook_path"]
        == "scripts/production_landing_text_quality_check.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_pilot_evidence_bundle"]["runbook_path"]
        == "scripts/production_pilot_evidence_bundle.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["operations_console_landing_smoke"]["runbook_path"]
        == "scripts/operations_console_landing_smoke.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["controlled_pilot_operator_packet"]["runbook_path"]
        == "docs/controlled_pilot_operator_packet_v48.md"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["controlled_pilot_console_verify"]["runbook_path"]
        == "scripts/controlled_pilot_console_verify.ps1"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["controlled_pilot_console_preflight"]["runbook_path"]
        == "scripts/controlled_pilot_console_preflight.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_landing_signoff_closeout_runbook"]["runbook_path"]
        == "docs/production_landing_signoff_closeout_runbook_v48.md"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_landing_pre_signoff_gate"]["runbook_path"]
        == "scripts/production_landing_pre_signoff_gate.py"
    )
    assert (
        data["observability"]["v4_evidence"]["entries"]["production_landing_signoff_reviewer_packet"]["runbook_path"]
        == "scripts/production_landing_signoff_reviewer_packet.py"
    )
    assert data["observability"]["frontend_production_build"]["status"] == "skipped"
    assert data["observability"]["frontend_production_build"]["build_executed"] is False
    assert data["observability"]["frontend_production_build"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_runtime_smoke"]["status"] == "skipped"
    assert data["observability"]["production_runtime_smoke"]["endpoint_check_count"] == 0
    assert data["observability"]["production_runtime_smoke"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_pilot_signoff"]["status"] == "skipped"
    assert data["observability"]["production_pilot_signoff"]["manual_signoff_required"] is True
    assert data["observability"]["production_pilot_signoff"]["manual_signoff_completed"] is False
    assert data["observability"]["production_pilot_signoff"]["manual_signoff_record_present"] is False
    assert data["observability"]["production_pilot_signoff"]["manual_signoff_package_status"] == "skipped"
    assert data["observability"]["production_pilot_signoff"]["closure_evidence_summary"]["closure_item_count"] == 0
    assert data["observability"]["production_pilot_signoff"]["closure_evidence_summary"]["latest_report"] == ""
    assert data["observability"]["production_pilot_signoff"]["enterprise_landing_state"] == "needs-local-evidence"
    assert data["observability"]["production_pilot_signoff"]["controlled_pilot_manual_review_ready"] is False
    assert data["observability"]["production_pilot_signoff"]["database_connected"] is False
    assert data["observability"]["production_pilot_signoff"]["redis_connected"] is False
    assert data["observability"]["production_pilot_signoff"]["external_mcp_connected"] is False
    assert data["observability"]["production_pilot_signoff"]["real_infra_ready"] is False
    assert data["observability"]["production_pilot_signoff"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_pilot_bootstrap"]["status"] == "skipped"
    assert data["observability"]["production_pilot_bootstrap"]["latest_report_present"] is False
    assert data["observability"]["production_pilot_bootstrap"]["signoff_closeout_passed"] is False
    assert data["observability"]["production_pilot_bootstrap"]["final_verification_passed"] is False
    assert data["observability"]["production_pilot_bootstrap"]["pilot_evidence_bundle_passed"] is False
    assert data["observability"]["production_pilot_bootstrap"]["operations_console_smoke_status"] == "skipped"
    assert data["observability"]["production_pilot_bootstrap"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_launch_gate"]["status"] == "blocked"
    assert data["observability"]["controlled_pilot_launch_gate"]["ready_for_controlled_pilot"] is False
    assert data["observability"]["controlled_pilot_launch_gate"]["controlled_pilot"] == "Manual-Review"
    assert data["observability"]["controlled_pilot_launch_gate"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_launch_gate"]["manual_signoff_required"] is True
    assert data["observability"]["controlled_pilot_launch_gate"]["missing_condition_count"] >= 1
    assert data["observability"]["controlled_pilot_launch_package"]["status"] == "skipped"
    assert data["observability"]["controlled_pilot_launch_package"]["latest_report_present"] is False
    assert data["observability"]["controlled_pilot_launch_package"]["launch_package_ready"] is False
    assert data["observability"]["controlled_pilot_launch_package"]["controlled_pilot"] == "Manual-Review"
    assert data["observability"]["controlled_pilot_launch_package"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_launch_package"]["business_data_written"] is False
    assert data["observability"]["controlled_pilot_launch_package"]["audit_data_written"] is False
    assert data["observability"]["controlled_pilot_launch_package"]["metrics_data_written"] is False
    assert data["observability"]["controlled_pilot_window_record"]["status"] == "skipped"
    assert data["observability"]["controlled_pilot_window_record"]["latest_report_present"] is False
    assert data["observability"]["controlled_pilot_window_record"]["opened"] is False
    assert data["observability"]["controlled_pilot_window_record"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_window_record"]["business_data_written"] is False
    assert data["observability"]["controlled_pilot_window_record"]["audit_data_written"] is False
    assert data["observability"]["controlled_pilot_window_record"]["metrics_data_written"] is False
    assert data["observability"]["controlled_pilot_window_status"]["status"] == "skipped"
    assert data["observability"]["controlled_pilot_window_status"]["latest_report_present"] is False
    assert data["observability"]["controlled_pilot_window_status"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_window_status"]["business_data_written"] is False
    assert data["observability"]["controlled_pilot_window_status"]["audit_data_written"] is False
    assert data["observability"]["controlled_pilot_window_status"]["metrics_data_written"] is False
    assert data["observability"]["business_system_read_smoke"]["status"] == "skipped"
    assert data["observability"]["business_system_read_smoke"]["business_system_connected"] is False
    assert data["observability"]["business_system_read_smoke"]["business_read_executed"] is False
    assert data["observability"]["business_system_read_smoke"]["business_write_executed"] is False
    assert data["observability"]["business_system_read_smoke"]["business_data_written"] is False
    assert data["observability"]["business_system_read_smoke"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["business_system_production_readiness"]["status"] == "skipped"
    assert data["observability"]["business_system_production_readiness"]["latest_report_present"] is False
    assert data["observability"]["business_system_production_readiness"]["missing_condition_count"] == 1
    assert (
        data["observability"]["business_system_production_readiness"]["missing_conditions"][0]
        == "business_system_production_readiness:report_not_found"
    )
    assert data["observability"]["business_system_production_readiness"]["business_write_executed"] is False
    assert data["observability"]["business_system_production_readiness"]["business_data_written"] is False
    assert data["observability"]["business_system_production_readiness"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["real_integration_staging_smoke"]["status"] == "skipped"
    assert data["observability"]["real_integration_staging_smoke"]["latest_report_present"] is False
    assert data["observability"]["real_integration_staging_smoke"]["read_only"] is True
    assert data["observability"]["real_integration_staging_smoke"]["execution_mode"] == "read_only_smoke"
    assert data["observability"]["real_integration_staging_smoke"]["preflight_summary"]["domain_count"] == 0
    assert data["observability"]["real_integration_staging_smoke"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["real_production_environment_checklist"]["status"] == "skipped"
    assert data["observability"]["real_production_environment_checklist"]["latest_report_present"] is False
    assert data["observability"]["real_production_environment_checklist"]["domain_count"] == 5
    assert data["observability"]["real_production_environment_checklist"]["domains"] == []
    assert data["observability"]["real_production_environment_checklist"]["next_commands"]["postgres"].endswith(
        "-Domains postgres"
    )
    assert (
        data["observability"]["real_production_environment_checklist"]["public_production_direct_launch"]
        == "No-Go"
    )
    assert data["observability"]["production_landing_input_readiness"]["status"] == "skipped"
    assert data["observability"]["production_landing_input_readiness"]["latest_report_present"] is False
    assert data["observability"]["production_landing_input_readiness"]["ready_input_count"] == 0
    assert data["observability"]["production_landing_input_readiness"]["required_input_count"] == 4
    assert data["observability"]["production_landing_input_readiness"]["missing_input_count"] == 4
    assert data["observability"]["production_landing_input_readiness"]["blocked_input_count"] == 0
    assert data["observability"]["production_landing_input_readiness"]["source_reports"] == {}
    assert data["observability"]["production_landing_input_readiness"]["resolved_paths"] == {}
    assert data["observability"]["production_landing_input_readiness"]["inputs"] == []
    assert data["observability"]["production_landing_input_readiness"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_input_readiness"]["auto_approved"] is False
    assert data["observability"]["production_landing_input_readiness"]["auto_closed"] is False
    assert data["observability"]["production_landing_env_check"]["status"] == "skipped"
    assert data["observability"]["production_landing_env_check"]["latest_report_present"] is False
    assert data["observability"]["production_landing_env_check"]["ready_domain_count"] == 0
    assert data["observability"]["production_landing_env_check"]["domain_count"] == 5
    assert data["observability"]["production_landing_env_check"]["domains"] == []
    assert data["observability"]["production_landing_env_check"]["blocked_domain_summaries"] == []
    assert data["observability"]["production_landing_env_check"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["manual_signoff_record_validation"]["status"] == "skipped"
    assert data["observability"]["manual_signoff_record_validation"]["latest_report_present"] is False
    assert data["observability"]["manual_signoff_record_validation"]["roles"] == []
    assert data["observability"]["manual_signoff_record_validation"]["evidence_acknowledgements"] == []
    assert data["observability"]["manual_signoff_record_validation"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["manual_signoff_record_promote"]["status"] == "skipped"
    assert data["observability"]["manual_signoff_record_promote"]["latest_report_present"] is False
    assert data["observability"]["manual_signoff_record_promote"]["promoted"] is False
    assert data["observability"]["manual_signoff_record_promote"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["manual_signoff_record_fill"]["status"] == "skipped"
    assert data["observability"]["manual_signoff_record_fill"]["latest_report_present"] is False
    assert data["observability"]["manual_signoff_record_fill"]["filled"] is False
    assert data["observability"]["manual_signoff_record_fill"]["manual_signoff_completed"] is False
    assert data["observability"]["manual_signoff_record_fill"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_signoff_closeout"]["status"] == "skipped"
    assert data["observability"]["production_landing_signoff_closeout"]["latest_report_present"] is False
    assert data["observability"]["production_landing_signoff_closeout"]["target_record_written"] is False
    assert data["observability"]["production_landing_signoff_closeout"]["steps"] == []
    assert data["observability"]["production_landing_signoff_closeout"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_pre_signoff_gate"]["status"] == "skipped"
    assert data["observability"]["production_landing_pre_signoff_gate"]["latest_report_present"] is False
    assert data["observability"]["production_landing_pre_signoff_gate"]["ready_for_manual_signoff"] is False
    assert data["observability"]["production_landing_pre_signoff_gate"]["non_signoff_blocker_count"] == 0
    assert data["observability"]["production_landing_pre_signoff_gate"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_signoff_reviewer_packet"]["status"] == "skipped"
    assert data["observability"]["production_landing_signoff_reviewer_packet"]["latest_report_present"] is False
    assert data["observability"]["production_landing_signoff_reviewer_packet"]["ready_for_manual_signoff"] is False
    assert data["observability"]["production_landing_signoff_reviewer_packet"]["evidence"] == []
    assert data["observability"]["production_landing_signoff_reviewer_packet"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_text_quality"]["status"] == "skipped"
    assert data["observability"]["production_landing_text_quality"]["latest_report_present"] is False
    assert data["observability"]["production_landing_text_quality"]["files"] == []
    assert data["observability"]["production_landing_text_quality"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_pilot_evidence_bundle"]["status"] == "skipped"
    assert data["observability"]["production_pilot_evidence_bundle"]["latest_report_present"] is False
    assert data["observability"]["production_pilot_evidence_bundle"]["controlled_pilot_ready"] is False
    assert data["observability"]["production_pilot_evidence_bundle"]["controlled_pilot"] == "Manual-Review"
    assert data["observability"]["production_pilot_evidence_bundle"]["sources"] == {}
    assert data["observability"]["production_pilot_evidence_bundle"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["operations_console_landing_smoke"]["status"] == "skipped"
    assert data["observability"]["operations_console_landing_smoke"]["latest_report_present"] is False
    assert data["observability"]["operations_console_landing_smoke"]["page_http_status"] is None
    assert data["observability"]["operations_console_landing_smoke"]["summary_http_status"] is None
    assert data["observability"]["operations_console_landing_smoke"]["backend_summary_http_status"] is None
    assert data["observability"]["operations_console_landing_smoke"]["acceptance_blockers"] == []
    assert data["observability"]["operations_console_landing_smoke"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_console_verify"]["status"] == "skipped"
    assert data["observability"]["controlled_pilot_console_verify"]["latest_report_present"] is False
    assert data["observability"]["controlled_pilot_console_verify"]["controlled_internal_pilot"] == "Manual-Review"
    assert data["observability"]["controlled_pilot_console_verify"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_console_verify"]["pid_file_present_after_verify"] is False
    assert data["observability"]["controlled_pilot_console_preflight"]["status"] == "skipped"
    assert data["observability"]["controlled_pilot_console_preflight"]["latest_report_present"] is False
    assert data["observability"]["controlled_pilot_console_preflight"]["ready_for_local_verify"] is False
    assert data["observability"]["controlled_pilot_console_preflight"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["controlled_pilot_console_preflight"]["blocking_conditions"] == []
    assert data["observability"]["production_landing_env_runner"]["status"] == "skipped"
    assert data["observability"]["production_landing_env_runner"]["latest_report_present"] is False
    assert data["observability"]["production_landing_env_runner"]["action"] == ""
    assert data["observability"]["production_landing_env_runner"]["return_code"] is None
    assert data["observability"]["production_landing_env_runner"]["child_status"] == ""
    assert data["observability"]["production_landing_env_runner"]["child_summary"]["status"] == ""
    assert data["observability"]["production_landing_env_runner"]["child_summary"]["ready_domain_count"] == 0
    assert data["observability"]["production_landing_env_runner"]["child_summary"]["domain_count"] == 0
    assert data["observability"]["production_landing_env_runner"]["child_summary"]["secret_plaintext_output"] is False
    assert data["observability"]["production_landing_env_runner"]["stdout"] == []
    assert data["observability"]["production_landing_env_runner"]["stderr"] == []
    assert data["observability"]["production_landing_env_runner"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_action_pack"]["status"] == "skipped"
    assert data["observability"]["production_landing_action_pack"]["latest_report_present"] is False
    assert data["observability"]["production_landing_action_pack"]["required_input_count"] == 0
    assert data["observability"]["production_landing_action_pack"]["required_inputs"] == []
    assert data["observability"]["production_landing_action_pack"]["recommended_commands"] == []
    assert data["observability"]["production_landing_action_pack"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_action_pack"]["auto_approved"] is False
    assert data["observability"]["production_landing_action_pack"]["auto_closed"] is False
    assert data["observability"]["production_landing_blocker_resolution"]["status"] == "skipped"
    assert data["observability"]["production_landing_blocker_resolution"]["latest_report_present"] is False
    assert data["observability"]["production_landing_blocker_resolution"]["required_action_count"] == 0
    assert data["observability"]["production_landing_blocker_resolution"]["required_actions"] == []
    assert data["observability"]["production_landing_blocker_resolution"]["actions"] == []
    assert data["observability"]["production_landing_blocker_resolution"]["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["production_landing_final_verification"]["status"] == "skipped"
    assert data["observability"]["production_landing_final_verification"]["latest_report_present"] is False
    assert data["observability"]["production_landing_final_verification"]["passed_count"] == 0
    assert data["observability"]["production_landing_final_verification"]["requirement_count"] == 0
    assert data["observability"]["production_landing_final_verification"]["requirements"] == []
    assert data["observability"]["production_landing_final_verification"]["missing_conditions"] == []
    assert data["observability"]["production_landing_final_verification"]["public_production_direct_launch"] == "No-Go"
    assert data["pilot_reports"]["directory_exists"] is False
    assert data["pilot_reports"]["total_reports"] == 0
    assert data["pilot_reports"]["reports"] == []
    text = json.dumps(data, ensure_ascii=False)
    for raw in ("sk-secret", "dbpassword", "redispassword", "raw_prompt_text"):
        assert raw not in text


def test_operations_summary_should_include_safe_aggregates(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    _write_report(tmp_path, "ops-report-1")

    from app.main import get_approval_store, get_audit_store, get_metrics_recorder, get_task_store

    task_store = get_task_store()
    task_store.save_task(
        TaskRun(task_id="task_ops_1", query="demo task", status=TaskStatus.completed),
        mode="keyword",
    )

    approval_store = get_approval_store()
    approval_store.create_approval(
        task_id="task_ops_1",
        tool_name="demo_tool",
        action="demo_action",
        payload={"query": "raw_query_text", "token": "approval-token"},
    )

    audit_store = get_audit_store()
    audit_store.append(
        AuditEvent(
            event_type="ops_summary_test",
            action="view_operations",
            detail={"prompt": "raw_prompt_text", "token": "audit-token", "request_id": "req-aud-001"},
        )
    )

    metrics = get_metrics_recorder()
    metrics.record_task(task_id="task_ops_1", mode="keyword", status="completed", latency_ms=12.0)
    metrics.record_token_usage(task_id="task_ops_1", prompt_tokens=21, completion_tokens=8, cost=0.11)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    text = json.dumps(data, ensure_ascii=False)

    assert data["health"]["version"] == "4.3.0"
    assert data["task_approval"]["task_count"] >= 1
    assert data["task_approval"]["approval_count"] >= 1
    assert data["pilot_reports"]["directory_exists"] is True
    assert data["pilot_reports"]["total_reports"] >= 1
    assert data["pilot_reports"]["reports"][0]["report_id"] == "ops-report-1"
    assert data["runtime_metrics"]["total_prompt_tokens"] >= 21
    assert data["runtime_metrics"]["total_cost"] >= 0.11
    assert data["audit"]["event_count"] >= 1
    assert data["observability"]["last_known_report_counts"]["pilot_reports"] >= 1
    assert data["observability"]["last_known_report_counts"]["audit_recent_events"] >= 1
    assert "v4_evidence_reports" in data["observability"]["last_known_report_counts"]
    assert "real_production_environment_checklist_reports" in data["observability"]["last_known_report_counts"]
    assert "real_production_environment_checklist" in data["observability"]["v4_evidence"]["entries"]
    assert "frontend_production_build" in data["observability"]["v4_evidence"]["entries"]
    assert "production_runtime_smoke" in data["observability"]["v4_evidence"]["entries"]
    assert "production_pilot_bootstrap" in data["observability"]["v4_evidence"]["entries"]
    assert "controlled_pilot_launch_gate" in data["observability"]["v4_evidence"]["entries"]
    assert "controlled_pilot_launch_package" in data["observability"]["v4_evidence"]["entries"]
    assert "controlled_pilot_window_record" in data["observability"]["v4_evidence"]["entries"]
    assert "controlled_pilot_window_status" in data["observability"]["v4_evidence"]["entries"]
    assert "production_pilot_signoff" in data["observability"]["v4_evidence"]["entries"]
    assert "business_system_read_smoke" in data["observability"]["v4_evidence"]["entries"]
    assert "business_system_production_readiness" in data["observability"]["v4_evidence"]["entries"]
    assert "production_landing_input_readiness" in data["observability"]["v4_evidence"]["entries"]
    assert "production_landing_action_pack" in data["observability"]["v4_evidence"]["entries"]
    assert "operations_console_landing_smoke" in data["observability"]["v4_evidence"]["entries"]
    assert data["observability"]["v4_evidence"]["boundary"]["auto_approved"] is False
    assert data["observability"]["v4_evidence"]["boundary"]["auto_closed"] is False
    assert "[REDACTED_PROMPT]" in text
    for raw in ("raw_prompt_text", "sk-secret", "dbpassword", "redispassword", "approval-token", "audit-token"):
        assert raw not in text


def test_operations_summary_should_include_production_pilot_bootstrap_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_pilot_bootstrap"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "skipped",
        "execute_real_smoke": False,
        "local_service_smoke": {"status": "success"},
        "evidence_count": 2,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_system_connected": False,
        "business_read_executed": False,
        "business_write_executed": False,
        "business_data_written": False,
        "auth_rbac_acceptance_passed": True,
        "signoff_closeout_passed": True,
        "final_verification_passed": True,
        "pilot_evidence_bundle_passed": True,
        "operations_console_smoke_status": "success",
        "auth_enabled": True,
        "rbac_enabled": True,
        "jwt_token_issued": True,
        "frontend_build_passed": True,
        "frontend_build_executed": True,
        "frontend_build_return_code": 0,
        "runtime_smoke_passed": True,
        "runtime_smoke_endpoint_check_count": 3,
        "secret_plaintext_output": False,
        "go_no_go": {"public_production_direct_launch": "No-Go"},
        "next_commands": {
            "real_llm": [
                "python scripts/production_pilot_bootstrap.py --execute-real-smoke --domains real_llm",
                "token=sk-should-not-leak",
                "api_key=tp-should-not-leak",
                "Authorization: Bearer should-not-leak",
            ]
        },
        "evidence_runs": [
            {"evidence_id": "real_integration_staging_smoke", "status": "skipped", "json_path": "docs/reports/demo.json"}
        ],
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    bootstrap = data["observability"]["production_pilot_bootstrap"]
    text = json.dumps(data, ensure_ascii=False)

    assert bootstrap["latest_report_present"] is True
    assert bootstrap["status"] == "skipped"
    assert bootstrap["local_service_status"] == "success"
    assert bootstrap["evidence_count"] == 2
    assert bootstrap["real_llm_executed"] is False
    assert bootstrap["business_system_connected"] is False
    assert bootstrap["business_read_executed"] is False
    assert bootstrap["business_write_executed"] is False
    assert bootstrap["business_data_written"] is False
    assert bootstrap["auth_rbac_acceptance_passed"] is True
    assert bootstrap["signoff_closeout_passed"] is True
    assert bootstrap["final_verification_passed"] is True
    assert bootstrap["pilot_evidence_bundle_passed"] is True
    assert bootstrap["operations_console_smoke_status"] == "success"
    assert bootstrap["auth_enabled"] is True
    assert bootstrap["rbac_enabled"] is True
    assert bootstrap["jwt_token_issued"] is True
    assert bootstrap["frontend_build_passed"] is True
    assert bootstrap["frontend_build_executed"] is True
    assert bootstrap["frontend_build_return_code"] == 0
    assert bootstrap["runtime_smoke_passed"] is True
    assert bootstrap["runtime_smoke_endpoint_check_count"] == 3
    assert bootstrap["public_production_direct_launch"] == "No-Go"
    assert bootstrap["evidence_runs"][0]["evidence_id"] == "real_integration_staging_smoke"
    assert "[redacted-secret-like-command]" in bootstrap["next_commands"]["real_llm"]
    assert data["observability"]["last_known_report_counts"]["production_pilot_bootstrap_reports"] == 1
    assert "sk-should-not-leak" not in text
    assert "tp-should-not-leak" not in text
    assert "should-not-leak" not in text


def test_operations_summary_should_include_frontend_production_build_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "frontend_production_build"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("FRONTEND_PRODUCTION_BUILD_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "execute": True,
        "build_executed": True,
        "return_code": 0,
        "frontend_dir_present": True,
        "package_json_present": True,
        "node_modules_present": True,
        "missing_conditions": [],
        "secret_plaintext_output": False,
        "go_no_go": {"public_production_direct_launch": "No-Go"},
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    frontend = data["observability"]["frontend_production_build"]

    assert frontend["latest_report_present"] is True
    assert frontend["status"] == "success"
    assert frontend["execute"] is True
    assert frontend["build_executed"] is True
    assert frontend["return_code"] == 0
    assert frontend["frontend_dir_present"] is True
    assert frontend["package_json_present"] is True
    assert frontend["node_modules_present"] is True
    assert frontend["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["frontend_production_build_reports"] == 1


def test_operations_summary_frontend_build_prefers_success_over_later_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "frontend_production_build"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("FRONTEND_PRODUCTION_BUILD_REPORT_DIR", str(report_dir))
    success_payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "execute": True,
        "build_executed": True,
        "return_code": 0,
        "frontend_dir_present": True,
        "package_json_present": True,
        "node_modules_present": True,
        "missing_conditions": [],
        "secret_plaintext_output": False,
        "go_no_go": {"public_production_direct_launch": "No-Go"},
    }
    skipped_payload = {
        **success_payload,
        "generated_at": "2026-06-04T00:01:00+00:00",
        "status": "skipped",
        "execute": False,
        "build_executed": False,
        "return_code": None,
        "missing_conditions": ["cli:--execute_not_requested"],
    }
    (report_dir / "001_success.json").write_text(json.dumps(success_payload, ensure_ascii=False), encoding="utf-8")
    (report_dir / "999_skipped.json").write_text(json.dumps(skipped_payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    frontend = response.json()["observability"]["frontend_production_build"]

    assert frontend["status"] == "success"
    assert frontend["build_executed"] is True
    assert frontend["return_code"] == 0


def test_operations_summary_should_include_production_runtime_smoke_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_runtime_smoke"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_RUNTIME_SMOKE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "endpoint_checks": [
            {"path": "/health", "http_status": 200, "passed": True},
            {"path": "/operations/summary", "http_status": 200, "passed": True},
            {"path": "/deployment/check", "http_status": 200, "passed": True},
        ],
        "operations_contract": {
            "status": "success",
            "frontend_build_status": "success",
            "frontend_build_executed": True,
            "bootstrap_status": "partial",
            "business_system_connected": False,
        },
        "secret_plaintext_output": False,
        "go_no_go": {"public_production_direct_launch": "No-Go"},
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    runtime = data["observability"]["production_runtime_smoke"]

    assert runtime["latest_report_present"] is True
    assert runtime["status"] == "success"
    assert runtime["endpoint_check_count"] == 3
    assert runtime["operations_contract_status"] == "success"
    assert runtime["frontend_build_status"] == "success"
    assert runtime["frontend_build_executed"] is True
    assert runtime["bootstrap_status"] == "partial"
    assert runtime["business_system_connected"] is False
    assert runtime["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_runtime_smoke_reports"] == 1


def test_operations_summary_should_include_production_pilot_signoff_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_pilot_signoff"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_PILOT_SIGNOFF_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "readiness_items": [{"item_id": "runtime_smoke_ready"}, {"item_id": "frontend_build_ready"}],
        "manual_signoff_required": True,
        "manual_signoff_completed": False,
        "manual_signoff_record_present": True,
        "manual_signoff_package_status": "success",
        "manual_signoff_roles": ["release_manager", "security_reviewer"],
        "manual_signoff_decision": "Go",
        "manual_signoff_blockers": [],
        "closure_evidence_summary": {
            "latest_report": "docs/reports/launch_blocker_closure/current.json",
            "report_count": 5,
            "closure_item_count": 13,
            "review_ready_count": 1,
            "evidence_missing_count": 0,
            "evidence_incomplete_count": 12,
            "blocked_closure_count": 0,
        },
        "signoff_sections": [
            {
                "section": "closure_evidence_summary",
                "latest_report": "docs/reports/launch_blocker_closure/latest.json",
                "report_count": 4,
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
            }
        ],
        "auto_signed": False,
        "auto_approved": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "recommendation": "Manual-Review",
            "production_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
        },
        "landing_status": {
            "enterprise_landing_state": "controlled-pilot-manual-review",
            "controlled_pilot_manual_review_ready": True,
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": False,
            "real_infra_ready": False,
            "production_blockers": [
                "business_system_read:not_executed",
                "real_infra:postgres_redis_mcp_not_all_connected",
            ],
        },
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    signoff = data["observability"]["production_pilot_signoff"]

    assert signoff["latest_report_present"] is True
    assert signoff["status"] == "partial"
    assert signoff["readiness_item_count"] == 2
    assert signoff["manual_signoff_required"] is True
    assert signoff["manual_signoff_completed"] is False
    assert signoff["manual_signoff_record_present"] is True
    assert signoff["manual_signoff_package_status"] == "success"
    assert signoff["manual_signoff_roles"] == ["release_manager", "security_reviewer"]
    assert signoff["manual_signoff_decision"] == "Go"
    assert signoff["manual_signoff_blockers"] == []
    assert signoff["closure_evidence_summary"]["latest_report"] == "docs/reports/launch_blocker_closure/latest.json"
    assert signoff["closure_evidence_summary"]["report_count"] == 4
    assert signoff["closure_evidence_summary"]["closure_item_count"] == 13
    assert signoff["closure_evidence_summary"]["review_ready_count"] == 0
    assert signoff["closure_evidence_summary"]["evidence_missing_count"] == 0
    assert signoff["closure_evidence_summary"]["evidence_incomplete_count"] == 13
    assert signoff["closure_evidence_summary"]["blocked_closure_count"] == 0
    assert signoff["closure_evidence_summary"]["evidence_readiness_summary"]["local_evidence_available_count"] == 12
    assert signoff["closure_evidence_summary"]["evidence_readiness_summary"]["runbook_only_count"] == 1
    assert signoff["closure_evidence_summary"]["evidence_readiness_summary"]["missing_count"] == 0
    assert signoff["closure_evidence_summary"]["evidence_readiness_summary"]["manual_review_required"] is True
    assert signoff["auto_signed"] is False
    assert signoff["auto_approved"] is False
    assert signoff["recommendation"] == "Manual-Review"
    assert signoff["production_pilot"] == "Manual-Review"
    assert signoff["enterprise_landing_state"] == "controlled-pilot-manual-review"
    assert signoff["controlled_pilot_manual_review_ready"] is True
    assert signoff["database_connected"] is True
    assert signoff["redis_connected"] is True
    assert signoff["external_mcp_connected"] is False
    assert signoff["real_infra_ready"] is False
    assert "business_system_read:not_executed" in signoff["production_blockers"]
    assert signoff["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_pilot_signoff_reports"] == 1


def test_operations_summary_pilot_signoff_reads_top_level_closure_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_pilot_signoff"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_PILOT_SIGNOFF_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "readiness_items": [],
        "manual_signoff_required": True,
        "manual_signoff_completed": False,
        "manual_signoff_record_present": True,
        "manual_signoff_package_status": "partial",
        "manual_signoff_blockers": ["manual_signoff:not_completed"],
        "closure_evidence_summary": {
            "latest_report": "docs/reports/launch_blocker_closure/current.json",
            "report_count": 4,
            "closure_item_count": 13,
            "review_ready_count": 0,
            "evidence_missing_count": 0,
            "evidence_incomplete_count": 13,
            "blocked_closure_count": 0,
        },
        "go_no_go": {"public_production_direct_launch": "No-Go"},
        "landing_status": {},
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    closure = response.json()["observability"]["production_pilot_signoff"]["closure_evidence_summary"]

    assert closure["latest_report"] == "docs/reports/launch_blocker_closure/current.json"
    assert closure["closure_item_count"] == 13
    assert closure["evidence_incomplete_count"] == 13


def test_operations_summary_should_include_business_system_read_smoke_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "business_system_read_smoke"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("BUSINESS_SYSTEM_READ_SMOKE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "skipped",
        "execute": False,
        "execution_requested": False,
        "read_only": True,
        "env_profile": {
            "execution_requested": False,
            "ready_for_execute": False,
            "required_env": [
                "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                "token=sk-should-not-leak",
            ],
            "auth_mode": "bearer",
            "safe_commands": {
                "interactive_powershell": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
                "api_key_header": 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -AuthHeaderName X-API-Key -AuthScheme ""',
            },
            "present": {"enabled": False, "write_tool_allowlist_empty": True},
            "public_production_gap": True,
            "next_action": "在本地环境填充真实只读 URL/token 后执行 python scripts/business_system_read_smoke.py --execute。",
        },
        "business_system_connected": False,
        "business_read_executed": False,
        "business_write_executed": False,
        "business_data_written": False,
        "approval_bypassed": False,
        "audit_bypassed": False,
        "missing_conditions": ["cli:--execute_not_requested"],
        "secret_plaintext_output": False,
        "go_no_go": {
            "business_system_read_smoke": "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    smoke = data["observability"]["business_system_read_smoke"]

    assert smoke["latest_report_present"] is True
    assert smoke["status"] == "skipped"
    assert smoke["execute"] is False
    assert smoke["execution_requested"] is False
    assert smoke["read_only"] is True
    assert smoke["env_profile"]["ready_for_execute"] is False
    assert smoke["env_profile"]["present"]["write_tool_allowlist_empty"] is True
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in smoke["env_profile"]["required_env"]
    assert "[redacted-secret-like-command]" in smoke["env_profile"]["required_env"]
    assert smoke["env_profile"]["auth_mode"] == "bearer"
    assert smoke["env_profile"]["public_production_gap"] is True
    assert smoke["env_profile"]["safe_commands"]["interactive_powershell"].endswith(
        "scripts\\business_system_read_smoke.ps1"
    )
    assert smoke["env_profile"]["next_action"].startswith("在本地环境填充真实只读")
    assert smoke["business_system_connected"] is False
    assert smoke["business_read_executed"] is False
    assert smoke["business_write_executed"] is False
    assert smoke["business_data_written"] is False
    assert smoke["approval_bypassed"] is False
    assert smoke["audit_bypassed"] is False
    assert smoke["business_system_read_smoke"] == "Needs-Input"
    assert smoke["public_production_direct_launch"] == "No-Go"
    assert smoke["manual_signoff_required"] is True
    assert data["observability"]["last_known_report_counts"]["business_system_read_smoke_reports"] == 1
    assert "sk-should-not-leak" not in json.dumps(data, ensure_ascii=False)


def test_operations_summary_should_include_business_system_production_readiness_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "business_system_production_readiness"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("BUSINESS_SYSTEM_PRODUCTION_READINESS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-06T00:00:00+00:00",
        "status": "needs_input",
        "read_only": True,
        "owner_inputs_present": {
            "business_owner": True,
            "security_reviewer": True,
            "operations_owner": False,
            "data_owner": True,
        },
        "required_inputs": [
            {
                "id": "read_only_secret",
                "description": "通过当前进程注入 token。",
                "env": "BUSINESS_SYSTEM_TOKEN_ENV / BUSINESS_SYSTEM_TOKEN",
                "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
            }
        ],
        "latest_business_smoke": {
            "latest_report_present": True,
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
        },
        "missing_conditions": ["evidence:business_system_real_read_smoke_not_executed"],
        "missing_condition_count": 1,
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_business_system_production_readiness.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    readiness = data["observability"]["business_system_production_readiness"]

    assert readiness["latest_report_present"] is True
    assert readiness["status"] == "needs_input"
    assert readiness["owner_inputs_present"]["operations_owner"] is False
    assert readiness["required_inputs"][0]["id"] == "read_only_secret"
    assert readiness["latest_business_smoke"]["business_read_executed"] is False
    assert readiness["latest_business_smoke"]["business_write_executed"] is False
    assert readiness["missing_condition_count"] == 1
    assert readiness["missing_conditions"] == ["evidence:business_system_real_read_smoke_not_executed"]
    assert readiness["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["business_system_production_readiness_reports"] == 1
    assert "sensitive-token" not in json.dumps(data, ensure_ascii=False)


def test_operations_summary_should_include_real_integration_staging_smoke_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "real_integration_staging_smoke"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "skipped",
        "mode": "dry_run_default",
        "read_only": True,
        "execution_mode": "read_only_smoke",
        "execute_requested": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "real_llm_executed": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "preflight_summary": {
            "ready_domain_count": 0,
            "domain_count": 2,
            "ready_domains": [],
            "blocked_domain_count": 0,
            "failed_domain_count": 0,
            "all_requested_domains_ready_for_execute": False,
            "domains": [
                {
                    "domain_id": "postgres",
                    "status": "skipped",
                    "execution_allowed": False,
                    "execution_invoked": False,
                    "ready_for_execute": False,
                    "missing_count": 3,
                    "env_present": {"DATABASE_URL": False},
                    "required_env": [
                        "DATABASE_URL=<secret-managed-url>",
                        "DATABASE_URL=postgresql://agent:should-not-leak@localhost/app",
                    ],
                    "next_action": "补齐本域 required_env 后重新执行 real_integration_staging_smoke.py --execute。",
                },
                {
                    "domain_id": "redis",
                    "status": "skipped",
                    "execution_allowed": False,
                    "execution_invoked": False,
                    "ready_for_execute": False,
                    "missing_count": 4,
                    "env_present": {"REDIS_URL": False},
                    "required_env": ["REDIS_URL=<secret-managed-url>"],
                    "next_action": "补齐本域 required_env 后重新执行 real_integration_staging_smoke.py --execute。",
                },
            ],
        },
        "missing_conditions": ["cli:--execute_not_requested"],
        "go_no_go": {"public_production_direct_launch": "No-Go"},
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    smoke = data["observability"]["real_integration_staging_smoke"]
    text = json.dumps(data, ensure_ascii=False)

    assert smoke["latest_report_present"] is True
    assert smoke["status"] == "skipped"
    assert smoke["read_only"] is True
    assert smoke["execution_mode"] == "read_only_smoke"
    assert smoke["database_connected"] is False
    assert smoke["redis_connected"] is False
    assert smoke["external_mcp_connected"] is False
    assert smoke["preflight_summary"]["domain_count"] == 2
    assert smoke["preflight_summary"]["domains"][0]["domain_id"] == "postgres"
    assert smoke["preflight_summary"]["domains"][0]["missing_count"] == 3
    assert "DATABASE_URL=<secret-managed-url>" in smoke["preflight_summary"]["domains"][0]["required_env"]
    assert "[redacted-secret-like-command]" in smoke["preflight_summary"]["domains"][0]["required_env"]
    assert smoke["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["real_integration_staging_smoke_reports"] == 1
    assert "should-not-leak" not in text


def test_operations_summary_should_include_production_landing_action_pack_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_action_pack"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_ACTION_PACK_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "required_input_count": 4,
        "required_inputs": [
            {
                "input_id": "business_system_read_only_credentials",
                "status": "required",
                "template": "docs/reports/business_system_read_smoke/business_read_smoke.env.template",
                "command_after_fill": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
            },
            {
                "input_id": "manual_signoff_record",
                "status": "required",
                "template": "docs/reports/manual_signoff_package/manual_signoff_record.template.json",
                "filled_record": "docs/reports/manual_signoff_package/manual_signoff_record.json",
                "draft": "token=sk-should-not-leak",
                "blocking_evidence_items": [
                    {
                        "item": "real_llm_preflight",
                        "source_status": "skipped",
                        "missing_conditions": ["real_llm_preflight:status_not_success"],
                        "acceptance_blockers": [
                            "missing_process_env:XIAOMI_LLM_API_KEY",
                            "token=sk-should-not-leak",
                        ],
                        "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                        "safe_commands": [
                            "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1",
                            "Authorization: Bearer should-not-leak",
                        ],
                    }
                ],
                "command_after_fill": "token=sk-should-not-leak",
                "promote_command_after_manual_fill": (
                    "python scripts/manual_signoff_record_promote.py "
                    "--source-record docs/reports/manual_signoff_package/manual_signoff_record.draft.json "
                    "--target-record docs/reports/manual_signoff_package/manual_signoff_record.json"
                ),
            },
            {
                "input_id": "real_infra_current_round_acceptance",
                "status": "required",
                "template": ".env.production.example",
                "draft": "set opt-in locally",
                "required_domains": "postgres,redis,external_mcp",
                "required_env": [
                    "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
                    "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                    "DATABASE_URL=postgresql://agent:should-not-leak@localhost/app",
                ],
                "command_after_fill": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres",
                "process_env_only_llm_preflight_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1",
            },
        ],
        "recommended_commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
            "Authorization: Bearer should-not-leak",
        ],
        "templates": {
            "manual_signoff_record_template": {
                "path": "docs/reports/manual_signoff_package/manual_signoff_record.template.json",
                "exists": True,
                "size_bytes": 123,
            }
        },
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    action_pack = data["observability"]["production_landing_action_pack"]
    text = json.dumps(data, ensure_ascii=False)

    assert action_pack["latest_report_present"] is True
    assert action_pack["status"] == "partial"
    assert action_pack["required_input_count"] == 4
    assert action_pack["required_inputs"][0]["input_id"] == "business_system_read_only_credentials"
    assert action_pack["required_inputs"][0]["command_after_fill"] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
    assert action_pack["required_inputs"][1]["draft"] == "[redacted-secret-like-command]"
    assert action_pack["required_inputs"][1]["filled_record"].endswith("manual_signoff_record.json")
    assert action_pack["required_inputs"][1]["blocking_evidence_items"][0]["item"] == "real_llm_preflight"
    assert (
        action_pack["required_inputs"][1]["blocking_evidence_items"][0]["safe_next_action"]
        == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    )
    assert (
        action_pack["required_inputs"][1]["blocking_evidence_items"][0]["acceptance_blockers"][0]
        == "missing_process_env:XIAOMI_LLM_API_KEY"
    )
    assert (
        action_pack["required_inputs"][1]["blocking_evidence_items"][0]["acceptance_blockers"][1]
        == "[redacted-secret-like-command]"
    )
    assert action_pack["required_inputs"][1]["blocking_evidence_items"][0]["safe_commands"][0] == (
        "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1"
    )
    assert action_pack["required_inputs"][1]["blocking_evidence_items"][0]["safe_commands"][1] == (
        "[redacted-secret-like-command]"
    )
    assert action_pack["required_inputs"][1]["command_after_fill"] == "[redacted-secret-like-command]"
    assert "manual_signoff_record_promote.py" in action_pack["required_inputs"][1]["promote_command_after_manual_fill"]
    assert action_pack["required_inputs"][2]["input_id"] == "real_infra_current_round_acceptance"
    assert action_pack["required_inputs"][2]["required_domains"] == "postgres,redis,external_mcp"
    assert "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true" in action_pack["required_inputs"][2]["required_env"]
    assert "XIAOMI_LLM_API_KEY=<secret-managed-token>" in action_pack["required_inputs"][2]["required_env"]
    assert "[redacted-secret-like-command]" in action_pack["required_inputs"][2]["required_env"]
    assert action_pack["required_inputs"][2]["process_env_only_llm_preflight_command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
    )
    assert action_pack["recommended_commands"][0] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
    assert action_pack["recommended_commands"][1] == "[redacted-secret-like-command]"
    assert action_pack["template_status"]["manual_signoff_record_template"]["exists"] is True
    assert action_pack["template_status"]["manual_signoff_record_template"]["size_bytes"] == 123
    assert action_pack["public_production_direct_launch"] == "No-Go"
    assert action_pack["auto_approved"] is False
    assert action_pack["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_action_pack_reports"] == 1
    assert "sk-should-not-leak" not in text
    assert "should-not-leak" not in text


def test_operations_summary_should_include_production_landing_blocker_resolution_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_blocker_resolution"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_BLOCKER_RESOLUTION_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "partial",
        "required_action_count": 2,
        "required_actions": ["real_llm_preflight", "manual_signoff_record"],
        "actions": [
            {
                "action_id": "real_llm_preflight",
                "status": "required",
                "owner": "operator",
                "evidence": {
                    "status": "skipped",
                    "api_key_present": False,
                    "network_check_requested": True,
                    "network_check_allowed": False,
                    "acceptance_blockers": ["missing_process_env:XIAOMI_LLM_API_KEY"],
                    "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                    "note": "token=sk-should-not-leak",
                },
                "safe_commands": [
                    "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1",
                    "Authorization: Bearer should-not-leak",
                ],
            }
        ],
        "source_blocked_or_failed": [],
        "source_missing_conditions": ["production_landing_final_verification"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_production_landing_blocker_resolution.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    resolution = data["observability"]["production_landing_blocker_resolution"]
    text = json.dumps(data, ensure_ascii=False)

    assert resolution["latest_report_present"] is True
    assert resolution["status"] == "partial"
    assert resolution["required_action_count"] == 2
    assert resolution["required_actions"] == ["real_llm_preflight", "manual_signoff_record"]
    assert resolution["actions"][0]["action_id"] == "real_llm_preflight"
    assert resolution["actions"][0]["evidence"]["network_check_requested"] == "True"
    assert resolution["actions"][0]["evidence"]["network_check_allowed"] == "False"
    assert resolution["actions"][0]["evidence"]["acceptance_blockers"] == ["missing_process_env:XIAOMI_LLM_API_KEY"]
    assert (
        resolution["actions"][0]["evidence"]["safe_next_action"]
        == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    )
    assert resolution["actions"][0]["evidence"]["note"] == "[redacted-secret-like-command]"
    assert resolution["actions"][0]["safe_commands"][0] == (
        "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1"
    )
    assert resolution["actions"][0]["safe_commands"][1] == "[redacted-secret-like-command]"
    assert resolution["source_missing_conditions"] == ["production_landing_final_verification"]
    assert resolution["public_production_direct_launch"] == "No-Go"
    assert resolution["auto_approved"] is False
    assert resolution["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_blocker_resolution_reports"] == 1
    assert "sk-should-not-leak" not in text
    assert "should-not-leak" not in text


def test_operations_summary_should_include_production_landing_final_verification_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_final_verification"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "partial",
        "passed_count": 3,
        "requirement_count": 8,
        "missing_conditions": [
            "real_llm_preflight:not_success",
            "token=sk-should-not-leak",
        ],
        "requirements": [
            {
                "requirement_id": "real_llm_preflight_success",
                "passed": False,
                "evidence": {"note": "token=sk-should-not-leak"},
                "missing_conditions": [
                    "real_llm_preflight:not_success",
                    "token=sk-should-not-leak",
                ],
            },
            {
                "requirement_id": "safe_no_public_direct_launch",
                "passed": True,
                "missing_conditions": [],
            },
        ],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_production_landing_final_verification.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    verification = data["observability"]["production_landing_final_verification"]
    text = json.dumps(data, ensure_ascii=False)

    assert verification["latest_report_present"] is True
    assert verification["status"] == "partial"
    assert verification["passed_count"] == 3
    assert verification["requirement_count"] == 8
    assert verification["missing_conditions"][0] == "real_llm_preflight:not_success"
    assert verification["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert verification["requirements"][0]["requirement_id"] == "real_llm_preflight_success"
    assert verification["requirements"][0]["passed"] is False
    assert verification["requirements"][0]["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert verification["requirements"][1]["passed"] is True
    assert verification["public_production_direct_launch"] == "No-Go"
    assert verification["auto_approved"] is False
    assert verification["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_final_verification_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_pilot_evidence_bundle_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_pilot_evidence_bundle"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T07:10:00+00:00",
        "status": "success",
        "controlled_pilot_ready": True,
        "final_verification_passed_count": 9,
        "final_verification_requirement_count": 9,
        "missing_condition_count": 0,
        "missing_conditions": [],
        "sources": {
            "production_landing_final_verification": {
                "source_id": "production_landing_final_verification",
                "present": True,
                "status": "success",
                "latest_json_path": str(report_dir / "safe.json"),
                "summary": {
                    "generated_at": "2026-06-05T07:09:00+00:00",
                    "passed_count": 9,
                    "requirement_count": 9,
                    "missing_condition_count": 0,
                    "secret_plaintext_output": False,
                    "public_production_direct_launch": "No-Go",
                },
                "missing_conditions": [],
                "secret_detected": False,
            },
            "production_landing_status": {
                "source_id": "production_landing_status",
                "present": True,
                "status": "success",
                "latest_json_path": "token=sk-should-not-leak",
                "summary": {
                    "generated_at": "2026-06-05T07:09:00+00:00",
                    "domain_count": 5,
                    "secret_plaintext_output": False,
                    "public_production_direct_launch": "No-Go",
                },
                "missing_conditions": ["token=sk-should-not-leak"],
                "secret_detected": True,
            },
        },
        "next_actions": ["进入有限企业内网受控试点窗口"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "go_no_go": {
            "controlled_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
    }
    (report_dir / "001_production_pilot_evidence_bundle.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    pilot_bundle = data["observability"]["production_pilot_evidence_bundle"]
    text = json.dumps(data, ensure_ascii=False)

    assert pilot_bundle["latest_report_present"] is True
    assert pilot_bundle["status"] == "success"
    assert pilot_bundle["controlled_pilot_ready"] is True
    assert pilot_bundle["controlled_pilot"] == "Go"
    assert pilot_bundle["final_verification_passed_count"] == 9
    assert pilot_bundle["final_verification_requirement_count"] == 9
    assert pilot_bundle["sources"]["production_landing_final_verification"]["passed_count"] == 9
    assert pilot_bundle["sources"]["production_landing_status"]["latest_json_path"] == "[redacted-secret-like-command]"
    assert pilot_bundle["sources"]["production_landing_status"]["missing_conditions"] == [
        "[redacted-secret-like-command]"
    ]
    assert pilot_bundle["sources"]["production_landing_status"]["secret_detected"] is True
    assert pilot_bundle["public_production_direct_launch"] == "No-Go"
    assert pilot_bundle["auto_approved"] is False
    assert pilot_bundle["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_pilot_evidence_bundle_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_controlled_pilot_launch_gate_ready_state(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    bundle_dir = tmp_path / "docs" / "reports" / "production_pilot_evidence_bundle"
    final_dir = tmp_path / "docs" / "reports" / "production_landing_final_verification"
    closeout_dir = tmp_path / "docs" / "reports" / "production_landing_signoff_closeout"
    bootstrap_dir = tmp_path / "docs" / "reports" / "production_pilot_bootstrap"
    for report_dir in (bundle_dir, final_dir, closeout_dir, bootstrap_dir):
        report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR", str(bundle_dir))
    monkeypatch.setenv("PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR", str(final_dir))
    monkeypatch.setenv("PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR", str(closeout_dir))
    monkeypatch.setenv("PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR", str(bootstrap_dir))

    (bundle_dir / "001_bundle.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T08:00:00+00:00",
                "status": "success",
                "controlled_pilot_ready": True,
                "final_verification_passed_count": 9,
                "final_verification_requirement_count": 9,
                "missing_condition_count": 0,
                "missing_conditions": [],
                "sources": {},
                "next_actions": ["start controlled pilot"],
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "auto_approved": False,
                "auto_closed": False,
                "go_no_go": {
                    "controlled_pilot": "Go",
                    "public_production_direct_launch": "No-Go",
                    "manual_signoff_required": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (final_dir / "001_final.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T08:00:01+00:00",
                "status": "success",
                "passed_count": 9,
                "requirement_count": 9,
                "missing_conditions": [],
                "requirements": [],
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "auto_approved": False,
                "auto_closed": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (closeout_dir / "001_closeout.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T08:00:02+00:00",
                "status": "success",
                "final_status": "success",
                "target_record_written": True,
                "steps": [],
                "missing_conditions": [],
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "auto_signed": False,
                "auto_approved": False,
                "auto_closed": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (bootstrap_dir / "001_bootstrap.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T08:00:03+00:00",
                "status": "partial",
                "local_service_smoke": {"status": "success"},
                "evidence_count": 17,
                "secret_plaintext_output": False,
                "go_no_go": {"public_production_direct_launch": "No-Go"},
                "next_commands": {},
                "evidence_runs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    gate = data["observability"]["controlled_pilot_launch_gate"]

    assert gate["status"] == "ready"
    assert gate["ready_for_controlled_pilot"] is True
    assert gate["controlled_pilot"] == "Go"
    assert gate["public_production_direct_launch"] == "No-Go"
    assert gate["manual_signoff_required"] is True
    assert gate["evidence_bundle_status"] == "success"
    assert gate["final_verification_status"] == "success"
    assert gate["signoff_closeout_status"] == "success"
    assert gate["bootstrap_status"] == "partial"
    assert gate["final_verification_passed_count"] == 9
    assert gate["final_verification_requirement_count"] == 9
    assert gate["missing_condition_count"] == 0
    assert gate["missing_conditions"] == []
    assert gate["safe_next_action"] == "start_controlled_internal_pilot_window"
    assert gate["operator_command"].endswith("scripts\\production_landing_signoff_closeout.ps1")
    assert gate["secret_plaintext_output"] is False
    assert gate["auto_approved"] is False
    assert gate["auto_closed"] is False


def test_operations_summary_should_include_controlled_pilot_launch_package_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_launch_package"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_LAUNCH_PACKAGE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T08:10:00+00:00",
        "status": "ready",
        "launch_package_ready": True,
        "controlled_pilot": "Go",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "missing_conditions": [],
        "missing_condition_count": 0,
        "safe_next_action": "open_controlled_pilot_window",
        "operator_commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\production_landing_signoff_closeout.ps1",
            "token=sk-should-not-leak",
        ],
        "pilot_roles": [
            {"role": "release_manager", "responsibility": "confirm launch window"},
            {"role": "security_reviewer", "responsibility": "confirm secret redaction"},
        ],
        "launch_window": {
            "scope": "controlled_internal_pilot",
            "public_production_direct_launch": "No-Go",
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
        },
        "sources": {
            "controlled_pilot_launch_gate": {
                "source_id": "controlled_pilot_launch_gate",
                "present": True,
                "status": "ready",
                "latest_json_path": "docs/reports/controlled_pilot_launch_gate/001.json",
                "generated_at": "2026-06-05T08:09:00+00:00",
                "summary": {
                    "ready_for_controlled_pilot": True,
                    "controlled_pilot": "Go",
                    "missing_condition_count": 0,
                    "safe_next_action": "start_controlled_internal_pilot_window",
                    "public_production_direct_launch": "No-Go",
                    "manual_signoff_required": True,
                    "secret_plaintext_output": False,
                },
                "missing_conditions": [],
                "secret_detected": False,
            },
            "production_pilot_evidence_bundle": {
                "source_id": "production_pilot_evidence_bundle",
                "present": True,
                "status": "success",
                "latest_json_path": "token=sk-should-not-leak",
                "generated_at": "2026-06-05T08:08:00+00:00",
                "summary": {"controlled_pilot_ready": True, "controlled_pilot": "Go"},
                "missing_conditions": ["token=sk-should-not-leak"],
                "secret_detected": True,
            },
        },
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_controlled_pilot_launch_package.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    package = data["observability"]["controlled_pilot_launch_package"]
    text = json.dumps(data, ensure_ascii=False)

    assert package["latest_report_present"] is True
    assert package["status"] == "ready"
    assert package["launch_package_ready"] is True
    assert package["controlled_pilot"] == "Go"
    assert package["public_production_direct_launch"] == "No-Go"
    assert package["manual_signoff_required"] is True
    assert package["safe_next_action"] == "open_controlled_pilot_window"
    assert package["operator_commands"][0].endswith("scripts\\production_landing_signoff_closeout.ps1")
    assert package["operator_commands"][1] == "[redacted-secret-like-command]"
    assert package["pilot_roles"][0]["role"] == "release_manager"
    assert package["launch_window"]["scope"] == "controlled_internal_pilot"
    assert package["launch_window"]["rollback_required"] is True
    assert package["sources"]["controlled_pilot_launch_gate"]["status"] == "ready"
    assert package["sources"]["production_pilot_evidence_bundle"]["latest_json_path"] == "[redacted-secret-like-command]"
    assert package["sources"]["production_pilot_evidence_bundle"]["missing_conditions"] == [
        "[redacted-secret-like-command]"
    ]
    assert package["sources"]["production_pilot_evidence_bundle"]["secret_detected"] is True
    assert package["business_data_written"] is False
    assert package["audit_data_written"] is False
    assert package["metrics_data_written"] is False
    assert package["auto_approved"] is False
    assert package["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_launch_package_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_controlled_pilot_window_record_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_window_record"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_WINDOW_RECORD_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T08:20:00+00:00",
        "status": "opened",
        "window_id": "controlled-pilot-test",
        "opened": True,
        "opened_by": "WYJ",
        "confirm_open": "YES",
        "controlled_pilot": "Go",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "launch_package": {
            "present": True,
            "status": "ready",
            "path": "docs/reports/controlled_pilot_launch_package/001.json",
            "launch_package_ready": True,
            "controlled_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 0,
            "safe_next_action": "open_controlled_pilot_window",
            "operator_command_count": 3,
            "pilot_role_count": 4,
            "source_count": 6,
            "secret_plaintext_output": False,
        },
        "missing_conditions": [],
        "missing_condition_count": 0,
        "rollback_required": True,
        "external_expansion_requires_new_manual_go_no_go": True,
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_controlled_pilot_window_record.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    record = data["observability"]["controlled_pilot_window_record"]

    assert record["latest_report_present"] is True
    assert record["status"] == "opened"
    assert record["window_id"] == "controlled-pilot-test"
    assert record["opened"] is True
    assert record["opened_by"] == "WYJ"
    assert record["confirm_open"] == "YES"
    assert record["controlled_pilot"] == "Go"
    assert record["public_production_direct_launch"] == "No-Go"
    assert record["launch_package"]["status"] == "ready"
    assert record["launch_package"]["launch_package_ready"] is True
    assert record["launch_package"]["operator_command_count"] == 3
    assert record["launch_package"]["pilot_role_count"] == 4
    assert record["launch_package"]["source_count"] == 6
    assert record["missing_condition_count"] == 0
    assert record["rollback_required"] is True
    assert record["external_expansion_requires_new_manual_go_no_go"] is True
    assert record["business_data_written"] is False
    assert record["audit_data_written"] is False
    assert record["metrics_data_written"] is False
    assert record["auto_approved"] is False
    assert record["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_window_record_reports"] == 1


def test_operations_summary_should_include_controlled_pilot_window_status_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_window_status"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_WINDOW_STATUS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T08:40:00+00:00",
        "status": "healthy",
        "window": {
            "present": True,
            "status": "opened",
            "path": "docs/reports/controlled_pilot_window_record/001.json",
            "opened": True,
            "window_id": "controlled-pilot-test",
            "opened_by": "WYJ",
            "controlled_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 0,
            "rollback_required": True,
            "launch_package_ready": True,
            "launch_package_status": "ready",
            "secret_plaintext_output": False,
        },
        "operations_summary": {
            "status": "success",
            "http_status": 200,
            "health_status": "ok",
            "deployment_ok": True,
            "deployment_error_count": 0,
            "deployment_warning_count": 1,
            "controlled_pilot_window_status": "opened",
            "controlled_pilot_window_opened": True,
            "controlled_pilot_window_id": "controlled-pilot-test",
            "launch_package_status": "ready",
            "launch_package_ready": True,
            "launch_gate_status": "ready",
            "launch_gate_ready": True,
            "public_production_direct_launch": "No-Go",
        },
        "missing_conditions": [],
        "missing_condition_count": 0,
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_controlled_pilot_window_status.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    status = data["observability"]["controlled_pilot_window_status"]

    assert status["latest_report_present"] is True
    assert status["status"] == "healthy"
    assert status["window"]["opened"] is True
    assert status["window"]["window_id"] == "controlled-pilot-test"
    assert status["window"]["launch_package_status"] == "ready"
    assert status["operations_summary"]["status"] == "success"
    assert status["operations_summary"]["health_status"] == "ok"
    assert status["operations_summary"]["deployment_ok"] is True
    assert status["operations_summary"]["deployment_warning_count"] == 1
    assert status["operations_summary"]["launch_gate_ready"] is True
    assert status["operations_summary"]["launch_package_ready"] is True
    assert status["missing_condition_count"] == 0
    assert status["public_production_direct_launch"] == "No-Go"
    assert status["business_data_written"] is False
    assert status["audit_data_written"] is False
    assert status["metrics_data_written"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_window_status_reports"] == 1


def test_operations_summary_should_include_production_landing_env_check_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_env_check"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_ENV_CHECK_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "env_file_present": True,
        "ready_domain_count": 1,
        "blocked_domain_count": 4,
        "domain_count": 5,
        "domains": [
            {
                "domain_id": "real_llm",
                "ready_for_execute": False,
                "blocker_reason": "placeholder_env",
                "next_action": "inject_xiaomi_api_key_in_process_env,run:powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1,rerun:python scripts/production_landing_env_check.py",
                "command_after_fill": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1",
                "required_env_keys": ["REAL_LLM_MODEL", "XIAOMI_LLM_API_KEY"],
                "missing_count": 0,
                "placeholder_count": 1,
                "mismatch_count": 0,
                "missing_keys": [],
                "placeholder_keys": ["XIAOMI_LLM_API_KEY"],
                "mismatch_keys": [],
                "keys": [{"key": "XIAOMI_LLM_API_KEY", "present": True, "placeholder": True}],
            },
            {
                "domain_id": "postgres",
                "ready_for_execute": True,
                "blocker_reason": "",
                "next_action": "run:powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres",
                "command_after_fill": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres",
                "required_env_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
                "missing_count": 0,
                "placeholder_count": 0,
                "mismatch_count": 0,
                "missing_keys": [],
                "placeholder_keys": [],
                "mismatch_keys": [],
            },
        ],
        "staging_smoke_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1 ; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres ; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis ; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp -McpServerCommand <approved-command> -McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>",
        "business_smoke_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    env_check = data["observability"]["production_landing_env_check"]

    assert env_check["latest_report_present"] is True
    assert env_check["status"] == "partial"
    assert env_check["env_file_present"] is True
    assert env_check["ready_domain_count"] == 1
    assert env_check["blocked_domain_count"] == 4
    assert env_check["domain_count"] == 5
    assert env_check["domains"][0]["domain_id"] == "real_llm"
    assert env_check["domains"][0]["blocker_reason"] == "placeholder_env"
    assert "inject_xiaomi_api_key_in_process_env" in env_check["domains"][0]["next_action"]
    assert "scripts/xiaomi_llm_landing_resume.ps1" in env_check["domains"][0]["next_action"]
    assert env_check["domains"][0]["command_after_fill"].endswith("scripts\\xiaomi_llm_preflight.ps1")
    assert env_check["domains"][0]["required_env_keys"] == ["REAL_LLM_MODEL", "XIAOMI_LLM_API_KEY"]
    assert env_check["domains"][0]["placeholder_keys"] == ["XIAOMI_LLM_API_KEY"]
    assert env_check["domains"][1]["ready_for_execute"] is True
    assert env_check["blocked_domain_summaries"] == [
        {
            "domain_id": "real_llm",
            "blocker_reason": "placeholder_env",
            "next_action": "inject_xiaomi_api_key_in_process_env,run:powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1,rerun:python scripts/production_landing_env_check.py",
            "missing_count": 0,
            "placeholder_count": 1,
            "mismatch_count": 0,
            "missing_keys": [],
            "placeholder_keys": ["XIAOMI_LLM_API_KEY"],
            "mismatch_keys": [],
        }
    ]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in env_check["staging_smoke_command"]
    assert env_check["business_smoke_command"] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
    assert env_check["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_env_check_reports"] == 1


def test_operations_summary_should_include_production_landing_env_runner_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_env_runner"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_ENV_RUNNER_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "action": "env-check",
        "env_file_present": True,
        "env_key_count": 29,
        "command": "python scripts/production_landing_env_check.py",
        "return_code": 0,
        "child_status": "partial",
        "child_summary": {
            "status": "partial",
            "ready_domain_count": 1,
            "domain_count": 5,
            "secret_plaintext_output": False,
        },
        "stdout": ["ok", "token=sk-should-not-leak"],
        "stderr": ["postgresql://user:should-not-leak@localhost/db"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    runner = data["observability"]["production_landing_env_runner"]
    text = json.dumps(data, ensure_ascii=False)

    assert runner["latest_report_present"] is True
    assert runner["status"] == "partial"
    assert runner["action"] == "env-check"
    assert runner["env_file_present"] is True
    assert runner["env_key_count"] == 29
    assert runner["command"] == "python scripts/production_landing_env_check.py"
    assert runner["return_code"] == 0
    assert runner["child_status"] == "partial"
    assert runner["child_summary"]["status"] == "partial"
    assert runner["child_summary"]["ready_domain_count"] == 1
    assert runner["child_summary"]["domain_count"] == 5
    assert runner["child_summary"]["secret_plaintext_output"] is False
    assert runner["stdout"][0] == "ok"
    assert "[redacted-secret-like-command]" in runner["stdout"]
    assert "[redacted-secret-like-command]" in runner["stderr"]
    assert runner["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_env_runner_reports"] == 1
    assert "should-not-leak" not in text


def test_operations_summary_should_include_xiaomi_llm_preflight_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_xiaomi_llm_preflight"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "api_key_env": "XIAOMI_LLM_API_KEY",
        "api_key_present": True,
        "real_llm_model": "mimo-v2.5-pro",
        "real_llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "execute_network_check": True,
        "preflight": {
            "network_check_requested": True,
            "network_check_allowed": True,
            "network_check_executed": True,
        },
        "real_llm_executed": True,
        "env_file_written": False,
        "local_env_modified": False,
        "safe_next_action": "refresh_landing_status_and_continue_manual_signoff",
        "acceptance_blockers": ["token=tp-should-not-leak"],
        "warnings": ["ok"],
        "errors": ["token=tp-should-not-leak"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001_production_landing_xiaomi_llm_preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    preflight = data["observability"]["production_landing_xiaomi_llm_preflight"]
    text = json.dumps(data, ensure_ascii=False)

    assert preflight["latest_report_present"] is True
    assert preflight["status"] == "success"
    assert preflight["api_key_env"] == "XIAOMI_LLM_API_KEY"
    assert preflight["api_key_present"] is True
    assert preflight["network_check_requested"] is True
    assert preflight["network_check_allowed"] is True
    assert preflight["network_check_executed"] is True
    assert preflight["real_llm_executed"] is True
    assert preflight["safe_next_action"] == "refresh_landing_status_and_continue_manual_signoff"
    assert preflight["acceptance_blockers"] == ["[redacted-secret-like-command]"]
    assert preflight["env_file_written"] is False
    assert preflight["local_env_modified"] is False
    assert preflight["errors"] == ["[redacted-secret-like-command]"]
    assert preflight["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_xiaomi_llm_preflight_reports"] == 1
    assert "tp-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_status_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_status"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_STATUS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "controlled_pilot_ready": False,
        "ready_domain_count": 4,
        "domain_count": 5,
        "blocked_domains": ["real_llm"],
        "blockers": ["execution_gate:not_allowed"],
        "next_commands": [
            "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1",
            "Authorization: Bearer should-not-leak",
        ],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001_production_landing_status.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    landing_status = data["observability"]["production_landing_status"]
    text = json.dumps(data, ensure_ascii=False)

    assert landing_status["latest_report_present"] is True
    assert landing_status["status"] == "partial"
    assert landing_status["controlled_pilot_ready"] is False
    assert landing_status["ready_domain_count"] == 4
    assert landing_status["domain_count"] == 5
    assert landing_status["blocked_domains"] == ["real_llm"]
    assert landing_status["blockers"] == ["execution_gate:not_allowed"]
    assert landing_status["next_commands"][0] == "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1"
    assert landing_status["next_commands"][1] == "[redacted-secret-like-command]"
    assert landing_status["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_status_reports"] == 1
    assert "should-not-leak" not in text


def test_operations_summary_prefers_latest_report_generated_at(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_status"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_STATUS_REPORT_DIR", str(report_dir))
    older = {
        "generated_at": "2026-06-04T20:00:00+00:00",
        "status": "success",
        "controlled_pilot_ready": True,
        "ready_domain_count": 5,
        "domain_count": 5,
        "blocked_domains": [],
        "blockers": [],
        "next_commands": [],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    newer = {
        "generated_at": "2026-06-04T20:30:00+00:00",
        "status": "partial",
        "controlled_pilot_ready": False,
        "ready_domain_count": 4,
        "domain_count": 5,
        "blocked_domains": ["real_llm"],
        "blockers": ["execution_gate:not_allowed"],
        "next_commands": ["powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "999_production_landing_status.json").write_text(json.dumps(older, ensure_ascii=False), encoding="utf-8")
    (report_dir / "001_production_landing_status.json").write_text(json.dumps(newer, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    landing_status = response.json()["observability"]["production_landing_status"]

    assert landing_status["status"] == "partial"
    assert landing_status["generated_at"] == "2026-06-04T20:30:00+00:00"
    assert landing_status["blocked_domains"] == ["real_llm"]


def test_operations_summary_should_include_production_landing_execution_gate_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_execution_gate"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_EXECUTION_GATE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "env_file_present": True,
        "requested_domains": ["real_llm", "postgres"],
        "ready_domains": ["postgres"],
        "blocked_domains": ["real_llm"],
        "requested_domain_count": 2,
        "ready_domain_count": 1,
        "blocked_domain_count": 1,
        "all_requested_domains_ready_for_execute": False,
        "execution_allowed": False,
        "real_smoke_executed": False,
        "business_smoke_executed": False,
        "domains": [
            {
                "domain_id": "real_llm",
                "ready_for_execute": False,
                "blocker_reason": "placeholder_env",
                "next_action": "replace_placeholder_keys_in_local_env",
                "command_after_fill": "python scripts/real_integration_staging_smoke.py --execute --domains real_llm",
                "required_env_keys": ["REAL_LLM_MODEL", "XIAOMI_LLM_API_KEY"],
                "missing_keys": [],
                "placeholder_keys": ["XIAOMI_LLM_API_KEY"],
                "mismatch_keys": [],
            }
        ],
        "safe_runner_commands": [
            "python scripts/production_landing_env_runner.py --action env-check",
            "Authorization: Bearer should-not-leak",
        ],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    gate = data["observability"]["production_landing_execution_gate"]
    text = json.dumps(data, ensure_ascii=False)

    assert gate["latest_report_present"] is True
    assert gate["status"] == "partial"
    assert gate["env_file_present"] is True
    assert gate["execution_allowed"] is False
    assert gate["ready_domains"] == ["postgres"]
    assert gate["blocked_domains"] == ["real_llm"]
    assert gate["ready_domain_count"] == 1
    assert gate["blocked_domain_count"] == 1
    assert gate["domains"][0]["blocker_reason"] == "placeholder_env"
    assert gate["safe_runner_commands"][0] == "python scripts/production_landing_env_runner.py --action env-check"
    assert gate["safe_runner_commands"][1] == "[redacted-secret-like-command]"
    assert gate["real_smoke_executed"] is False
    assert gate["business_smoke_executed"] is False
    assert gate["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_execution_gate_reports"] == 1
    assert "should-not-leak" not in text


def test_operations_summary_should_include_production_landing_input_readiness_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_input_readiness"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_INPUT_READINESS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "ready_input_count": 1,
        "required_input_count": 4,
        "missing_input_count": 3,
        "blocked_input_count": 0,
        "source_reports": {
            "business_env": "docs/reports/business_system_read_smoke/business_read_smoke.env.template",
            "pilot_signoff": "docs/reports/production_pilot_signoff/current.json",
        },
        "resolved_paths": {
            "business_env": "docs/reports/business_system_read_smoke/business_read_smoke.env.template",
            "pilot_signoff": "docs/reports/production_pilot_signoff/current.json",
        },
        "inputs": [
            {
                "input_id": "business_system_read_only_credentials",
                "path": "docs/reports/business_system_read_smoke/business_read_smoke.env.template",
                "present": True,
                "status": "partial",
                "missing_conditions": [
                    "business_env:BUSINESS_SYSTEM_BASE_URL_not_filled",
                    "token=sk-should-not-leak",
                ],
                "base_url_present": False,
                "token_present": False,
                "read_only": True,
                "write_enabled": False,
                "secret_plaintext_output": False,
                "next_action": "填写本地业务系统只读凭据后执行只读 smoke；不得提交真实 token。",
                "command_after_fill": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
                "required_env": [
                    "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
                    "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                    "token=sk-should-not-leak",
                ],
            },
            {
                "input_id": "launch_blocker_closure_evidence",
                "path": "docs/reports/launch_blocker_closure/closure_evidence.template.json",
                "present": True,
                "status": "partial",
                "missing_conditions": ["closure_evidence:LB-001:approval_state_not_ready"],
                "ready_count": 0,
                "closure_item_count": 13,
                "secret_plaintext_output": False,
                "auto_approved": False,
                "auto_closed": False,
            },
            {
                "input_id": "real_infra_current_round_acceptance",
                "path": "docs/reports/production_pilot_signoff/current.json",
                "present": True,
                "status": "partial",
                "missing_conditions": ["real_infra:postgres_redis_mcp_not_all_connected"],
                "database_connected": False,
                "redis_connected": False,
                "external_mcp_connected": True,
                "real_infra_ready": False,
                "secret_plaintext_output": False,
                "auto_approved": False,
                "auto_closed": False,
            },
        ],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    readiness = data["observability"]["production_landing_input_readiness"]
    text = json.dumps(data, ensure_ascii=False)

    assert readiness["latest_report_present"] is True
    assert readiness["status"] == "partial"
    assert readiness["ready_input_count"] == 1
    assert readiness["required_input_count"] == 4
    assert readiness["missing_input_count"] == 3
    assert readiness["blocked_input_count"] == 0
    assert readiness["source_reports"]["pilot_signoff"] == "docs/reports/production_pilot_signoff/current.json"
    assert readiness["resolved_paths"]["business_env"] == "docs/reports/business_system_read_smoke/business_read_smoke.env.template"
    assert readiness["inputs"][0]["input_id"] == "business_system_read_only_credentials"
    assert readiness["inputs"][0]["missing_count"] == 2
    assert readiness["inputs"][0]["read_only"] is True
    assert readiness["inputs"][0]["write_enabled"] is False
    assert readiness["inputs"][0]["next_action"].startswith("填写本地业务系统只读凭据")
    assert readiness["inputs"][0]["command_after_fill"] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in readiness["inputs"][0]["required_env"]
    assert "[redacted-secret-like-command]" in readiness["inputs"][0]["required_env"]
    assert readiness["inputs"][1]["ready_count"] == 0
    assert readiness["inputs"][1]["closure_item_count"] == 13
    assert readiness["inputs"][2]["input_id"] == "real_infra_current_round_acceptance"
    assert readiness["inputs"][2]["database_connected"] is False
    assert readiness["inputs"][2]["redis_connected"] is False
    assert readiness["inputs"][2]["external_mcp_connected"] is True
    assert readiness["inputs"][2]["real_infra_ready"] is False
    assert readiness["public_production_direct_launch"] == "No-Go"
    assert data["observability"]["last_known_report_counts"]["production_landing_input_readiness_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_manual_signoff_evidence_ack_status_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "manual_signoff_evidence_ack_status"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "partial",
        "items": [
            {
                "item": "real_llm_preflight",
                "latest_report": "docs/reports/production_landing_xiaomi_llm_preflight/latest.json",
                "report_present": True,
                "source_status": "skipped",
                "recommended_accept": False,
                "missing_conditions": [
                    "real_llm_preflight:status_not_success",
                    "token=sk-should-not-leak",
                ],
            },
            {
                "item": "postgres_redis_mcp_smoke",
                "latest_report": "docs/reports/real_integration_staging_smoke/latest.json",
                "report_present": True,
                "source_status": "success",
                "recommended_accept": True,
                "missing_conditions": [],
            },
            {
                "item": "business_read_smoke",
                "latest_report": "docs/reports/business_system_read_smoke/latest.json",
                "report_present": True,
                "source_status": "success",
                "recommended_accept": True,
                "missing_conditions": [],
            },
            {
                "item": "closure_evidence_review",
                "latest_report": "docs/reports/launch_blocker_closure/latest.json",
                "report_present": True,
                "source_status": "partial",
                "recommended_accept": True,
                "missing_conditions": [],
            },
        ],
        "item_count": 4,
        "recommended_accept_count": 3,
        "blocked_item_count": 0,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_manual_signoff_evidence_ack_status.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    ack_status = data["observability"]["manual_signoff_evidence_ack_status"]
    text = json.dumps(data, ensure_ascii=False)

    assert ack_status["latest_report_present"] is True
    assert ack_status["status"] == "partial"
    assert ack_status["recommended_accept_count"] == 3
    assert ack_status["item_count"] == 4
    assert ack_status["blocked_item_count"] == 0
    assert ack_status["items"][0]["item"] == "real_llm_preflight"
    assert ack_status["items"][0]["recommended_accept"] is False
    assert ack_status["items"][0]["missing_count"] == 2
    assert "[redacted-secret-like-command]" in ack_status["items"][0]["missing_conditions"]
    assert ack_status["items"][1]["recommended_accept"] is True
    assert ack_status["public_production_direct_launch"] == "No-Go"
    assert ack_status["auto_approved"] is False
    assert ack_status["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["manual_signoff_evidence_ack_status_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_manual_signoff_record_validation_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "manual_signoff_record_validation"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("MANUAL_SIGNOFF_RECORD_VALIDATION_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "partial",
        "signoff_record_present": True,
        "ack_status": "partial",
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "roles": [
            {
                "role": "release_manager",
                "name_present": False,
                "approved": False,
                "responsibility": "token=sk-should-not-leak",
            },
            {"role": "security_reviewer", "name_present": True, "approved": False},
        ],
        "evidence_acknowledgements": [
            {
                "item": "real_llm_preflight",
                "accepted": False,
                "latest_report": "docs/reports/production_landing_xiaomi_llm_preflight/latest.json",
                "note_present": True,
            }
        ],
        "missing_conditions": [
            "manual_signoff_record:release_manager_not_approved",
            "token=sk-should-not-leak",
        ],
        "missing_condition_count": 2,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_manual_signoff_record_validation.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    validation = data["observability"]["manual_signoff_record_validation"]
    text = json.dumps(data, ensure_ascii=False)

    assert validation["latest_report_present"] is True
    assert validation["status"] == "partial"
    assert validation["signoff_record_present"] is True
    assert validation["ack_status"] == "partial"
    assert validation["manual_signoff_completed"] is False
    assert validation["decision"] == "No-Go"
    assert validation["roles"][0] == {"role": "release_manager", "name_present": False, "approved": False}
    assert validation["roles"][1]["role"] == "security_reviewer"
    assert validation["evidence_acknowledgements"][0]["item"] == "real_llm_preflight"
    assert validation["evidence_acknowledgements"][0]["accepted"] is False
    assert validation["missing_conditions"][0] == "manual_signoff_record:release_manager_not_approved"
    assert validation["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert validation["missing_condition_count"] == 2
    assert validation["public_production_direct_launch"] == "No-Go"
    assert validation["auto_approved"] is False
    assert validation["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["manual_signoff_record_validation_reports"] == 1
    assert "sk-should-not-leak" not in text
    assert "responsibility" not in json.dumps(validation, ensure_ascii=False)


def test_operations_summary_should_include_manual_signoff_record_promote_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "manual_signoff_record_promote"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("MANUAL_SIGNOFF_RECORD_PROMOTE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T01:30:00+00:00",
        "status": "partial",
        "source_record": "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
        "target_record": "docs/reports/manual_signoff_package/manual_signoff_record.json",
        "source_record_present": True,
        "target_record_written": False,
        "promoted": False,
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "missing_conditions": [
            "manual_signoff_record:not_completed",
            "token=sk-should-not-leak",
        ],
        "missing_condition_count": 2,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_manual_signoff_record_promote.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    promote = data["observability"]["manual_signoff_record_promote"]
    text = json.dumps(data, ensure_ascii=False)

    assert promote["latest_report_present"] is True
    assert promote["status"] == "partial"
    assert promote["source_record_present"] is True
    assert promote["target_record_written"] is False
    assert promote["promoted"] is False
    assert promote["manual_signoff_completed"] is False
    assert promote["decision"] == "No-Go"
    assert promote["missing_conditions"][0] == "manual_signoff_record:not_completed"
    assert promote["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert promote["missing_condition_count"] == 2
    assert promote["public_production_direct_launch"] == "No-Go"
    assert promote["auto_approved"] is False
    assert promote["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["manual_signoff_record_promote_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_manual_signoff_record_fill_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "manual_signoff_record_fill"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("MANUAL_SIGNOFF_RECORD_FILL_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T02:00:00+00:00",
        "status": "partial",
        "signoff_record": "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
        "filled": False,
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "missing_conditions": [
            "manual_signoff_record_fill:confirm_manual_signoff_required",
            "token=sk-should-not-leak",
        ],
        "missing_condition_count": 2,
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_manual_signoff_record_fill.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    fill = data["observability"]["manual_signoff_record_fill"]
    text = json.dumps(data, ensure_ascii=False)

    assert fill["latest_report_present"] is True
    assert fill["status"] == "partial"
    assert fill["signoff_record"] == "docs/reports/manual_signoff_package/manual_signoff_record.draft.json"
    assert fill["filled"] is False
    assert fill["manual_signoff_completed"] is False
    assert fill["decision"] == "No-Go"
    assert fill["missing_conditions"][0] == "manual_signoff_record_fill:confirm_manual_signoff_required"
    assert fill["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert fill["missing_condition_count"] == 2
    assert fill["public_production_direct_launch"] == "No-Go"
    assert fill["auto_signed"] is False
    assert fill["auto_approved"] is False
    assert fill["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["manual_signoff_record_fill_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_signoff_closeout_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_signoff_closeout"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T02:10:00+00:00",
        "status": "partial",
        "final_status": "",
        "signoff_record": "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
        "target_record": "docs/reports/manual_signoff_package/manual_signoff_record.json",
        "target_record_written": False,
        "steps": [
            {
                "step_id": "manual_signoff_record_fill",
                "status": "partial",
                "json_path": "docs/reports/manual_signoff_record_fill/001.json",
                "secret_plaintext_output": False,
            }
        ],
        "missing_conditions": [
            "production_landing_signoff_closeout:confirm_manual_signoff_required",
            "token=sk-should-not-leak",
        ],
        "missing_condition_count": 2,
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_production_landing_signoff_closeout.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    closeout = data["observability"]["production_landing_signoff_closeout"]
    text = json.dumps(data, ensure_ascii=False)

    assert closeout["latest_report_present"] is True
    assert closeout["status"] == "partial"
    assert closeout["final_status"] == ""
    assert closeout["target_record_written"] is False
    assert closeout["steps"][0]["step_id"] == "manual_signoff_record_fill"
    assert closeout["steps"][0]["status"] == "partial"
    assert closeout["missing_conditions"][0] == "production_landing_signoff_closeout:confirm_manual_signoff_required"
    assert closeout["missing_conditions"][1] == "[redacted-secret-like-command]"
    assert closeout["missing_condition_count"] == 2
    assert closeout["public_production_direct_launch"] == "No-Go"
    assert closeout["auto_signed"] is False
    assert closeout["auto_approved"] is False
    assert closeout["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_signoff_closeout_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_pre_signoff_gate_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_pre_signoff_gate"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_PRE_SIGNOFF_GATE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T02:20:00+00:00",
        "status": "ready_for_manual_signoff",
        "ready_for_manual_signoff": True,
        "technical_evidence_ready": True,
        "ack_ready": True,
        "action_required_input_count": 1,
        "non_signoff_blockers": ["token=sk-should-not-leak"],
        "non_signoff_blocker_count": 1,
        "signoff_only_missing_conditions": ["manual_signoff:not_completed"],
        "status_blockers": ["manual_signoff:not_completed"],
        "final_missing_conditions": ["manual_signoff:not_completed"],
        "closeout_missing_conditions": ["production_landing_signoff_closeout:confirm_manual_signoff_required"],
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_production_landing_pre_signoff_gate.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    gate = data["observability"]["production_landing_pre_signoff_gate"]
    text = json.dumps(data, ensure_ascii=False)

    assert gate["latest_report_present"] is True
    assert gate["status"] == "ready_for_manual_signoff"
    assert gate["ready_for_manual_signoff"] is True
    assert gate["technical_evidence_ready"] is True
    assert gate["ack_ready"] is True
    assert gate["action_required_input_count"] == 1
    assert gate["non_signoff_blockers"][0] == "[redacted-secret-like-command]"
    assert gate["non_signoff_blocker_count"] == 1
    assert gate["signoff_only_missing_conditions"][0] == "manual_signoff:not_completed"
    assert gate["public_production_direct_launch"] == "No-Go"
    assert gate["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_pre_signoff_gate_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_signoff_reviewer_packet_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_signoff_reviewer_packet"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T02:30:00+00:00",
        "status": "ready_for_review",
        "ready_for_manual_signoff": True,
        "technical_evidence_ready": True,
        "non_signoff_blocker_count": 0,
        "ack_ready": True,
        "missing_conditions": ["token=sk-should-not-leak"],
        "missing_condition_count": 1,
        "recommended_closeout_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\production_landing_signoff_closeout.ps1",
        "evidence": [
            {
                "source_id": "pre_signoff_gate",
                "status": "ready_for_manual_signoff",
                "latest_report_present": True,
                "latest_json_path": "pre.json",
                "secret_plaintext_output": False,
            }
        ],
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_production_landing_signoff_reviewer_packet.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    packet = data["observability"]["production_landing_signoff_reviewer_packet"]
    text = json.dumps(data, ensure_ascii=False)

    assert packet["latest_report_present"] is True
    assert packet["status"] == "ready_for_review"
    assert packet["ready_for_manual_signoff"] is True
    assert packet["technical_evidence_ready"] is True
    assert packet["ack_ready"] is True
    assert packet["non_signoff_blocker_count"] == 0
    assert packet["missing_conditions"][0] == "[redacted-secret-like-command]"
    assert packet["evidence"][0]["source_id"] == "pre_signoff_gate"
    assert packet["evidence"][0]["status"] == "ready_for_manual_signoff"
    assert packet["recommended_closeout_command"].endswith("scripts\\production_landing_signoff_closeout.ps1")
    assert packet["public_production_direct_launch"] == "No-Go"
    assert packet["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_signoff_reviewer_packet_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_text_quality_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_text_quality"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "success",
        "checked_file_count": 2,
        "blocked_file_count": 0,
        "files": [
            {
                "path": "docs/production_landing_operator_runbook_v47.md",
                "exists": True,
                "status": "success",
                "mojibake_markers": [],
                "secret_like_detected": False,
                "missing_conditions": [],
            },
            {
                "path": "docs/xiaomi_llm_landing_resume_runbook_v47.md",
                "exists": True,
                "status": "blocked",
                "mojibake_markers": ["琛"],
                "secret_like_detected": True,
                "missing_conditions": ["token=sk-should-not-leak"],
            },
        ],
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_production_landing_text_quality.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    quality = data["observability"]["production_landing_text_quality"]
    text = json.dumps(data, ensure_ascii=False)

    assert quality["latest_report_present"] is True
    assert quality["status"] == "success"
    assert quality["checked_file_count"] == 2
    assert quality["blocked_file_count"] == 0
    assert quality["files"][0]["status"] == "success"
    assert quality["files"][1]["mojibake_markers"] == ["琛"]
    assert quality["files"][1]["secret_like_detected"] is True
    assert quality["files"][1]["missing_conditions"] == ["[redacted-secret-like-command]"]
    assert quality["public_production_direct_launch"] == "No-Go"
    assert quality["auto_approved"] is False
    assert quality["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_text_quality_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_business_system_input_packet_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "business_system_input_packet"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("BUSINESS_SYSTEM_INPUT_PACKET_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-06T00:00:00+00:00",
        "status": "needs_input",
        "ready_for_real_read_smoke": False,
        "owner_inputs_present": {
            "business_owner": False,
            "security_reviewer": True,
        },
        "config": {
            "enabled": False,
            "read_only": False,
            "write_enabled": False,
            "approval_required": False,
            "audit_required": False,
            "system_name": "crm",
            "base_url_env": "BUSINESS_SYSTEM_BASE_URL",
            "base_url_present": False,
            "token_env": "BUSINESS_SYSTEM_TOKEN",
            "token_present": False,
            "tool_allowlist_count": 1,
            "write_tool_allowlist_count": 0,
            "timeout_seconds": 5,
            "read_probe_path_configured": True,
            "auth_header_name": "Authorization",
            "auth_scheme_configured": True,
        },
        "missing_conditions": ["owner:business_owner_missing", "token=sk-should-not-leak"],
        "missing_condition_count": 2,
        "required_inputs": [
            {
                "id": "business_owner_chain",
                "env": ["BUSINESS_SYSTEM_BUSINESS_OWNER"],
                "description": "负责人",
            }
        ],
        "local_env_template_lines": [
            "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
            "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
        ],
        "manual_input_checklist": [
            {
                "id": "credential",
                "env": ["BUSINESS_SYSTEM_TOKEN"],
                "description": "只读 token",
            }
        ],
        "recommended_commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    (report_dir / "001_business_system_input_packet.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    packet = data["observability"]["business_system_input_packet"]
    text = json.dumps(data, ensure_ascii=False)

    assert packet["latest_report_present"] is True
    assert packet["status"] == "needs_input"
    assert packet["ready_for_real_read_smoke"] is False
    assert packet["owner_inputs_present"]["business_owner"] is False
    assert packet["config"]["base_url_env"] == "BUSINESS_SYSTEM_BASE_URL"
    assert packet["local_env_template_lines"][0] == "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>"
    assert packet["manual_input_checklist"][0]["id"] == "credential"
    assert packet["recommended_commands"][0].endswith("scripts\\business_system_read_smoke.ps1")
    assert packet["missing_conditions"] == ["owner:business_owner_missing", "[redacted-secret-like-command]"]
    assert packet["public_production_direct_launch"] == "No-Go"
    assert packet["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["business_system_input_packet_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_production_landing_evidence_freshness_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "production_landing_evidence_freshness"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("PRODUCTION_LANDING_EVIDENCE_FRESHNESS_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-06T00:00:00+00:00",
        "status": "partial",
        "current_commit": "abcdef1234567890",
        "worktree_clean": False,
        "source_count": 2,
        "stale_source_count": 1,
        "sources": [
            {
                "source_id": "production_landing_status",
                "present": True,
                "status": "partial",
                "generated_at": "2026-06-06T00:00:00+00:00",
                "report_commit": "abcdef1234567890",
                "commit_matches_head": True,
                "secret_like_detected": False,
                "missing_conditions": [],
            },
            {
                "source_id": "business_system_input_packet",
                "present": True,
                "status": "needs_input",
                "generated_at": "2026-06-06T00:00:00+00:00",
                "report_commit": "100cdc2",
                "commit_matches_head": False,
                "secret_like_detected": True,
                "missing_conditions": ["token=sk-should-not-leak"],
            },
        ],
        "missing_conditions": ["git:worktree_dirty", "token=sk-should-not-leak"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    (report_dir / "001_production_landing_evidence_freshness.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    freshness = data["observability"]["production_landing_evidence_freshness"]
    text = json.dumps(data, ensure_ascii=False)

    assert freshness["latest_report_present"] is True
    assert freshness["status"] == "partial"
    assert freshness["worktree_clean"] is False
    assert freshness["stale_source_count"] == 1
    assert freshness["source_count"] == 2
    assert freshness["sources"][0]["commit_matches_head"] is True
    assert freshness["sources"][1]["secret_like_detected"] is True
    assert freshness["sources"][1]["missing_conditions"] == ["[redacted-secret-like-command]"]
    assert freshness["missing_conditions"] == ["git:worktree_dirty", "[redacted-secret-like-command]"]
    assert freshness["public_production_direct_launch"] == "No-Go"
    assert freshness["auto_approved"] is False
    assert freshness["auto_closed"] is False
    assert data["observability"]["last_known_report_counts"]["production_landing_evidence_freshness_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_operations_console_landing_smoke_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "operations_console_landing_smoke"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T04:31:16+00:00",
        "status": "success",
        "execute": True,
        "page_http_status": 200,
        "summary_http_status": 200,
        "backend_summary_http_status": 200,
        "preflight_status": "success",
        "network_check_requested": True,
        "network_check_allowed": True,
        "safe_next_action": "refresh_landing_status_and_continue_manual_signoff",
        "acceptance_blockers": [],
        "blocker_action_present": True,
        "blocker_safe_next_action": "manual_signoff_record_required",
        "blocker_acceptance_blockers": ["token=sk-should-not-leak"],
        "missing_conditions": ["manual_signoff:not_completed"],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    (report_dir / "001_operations_console_landing_smoke.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    smoke = data["observability"]["operations_console_landing_smoke"]
    text = json.dumps(data, ensure_ascii=False)

    assert smoke["latest_report_present"] is True
    assert smoke["selection"] == "latest_successful_executed"
    assert smoke["status"] == "success"
    assert smoke["execute"] is True
    assert smoke["page_http_status"] == 200
    assert smoke["summary_http_status"] == 200
    assert smoke["backend_summary_http_status"] == 200
    assert smoke["preflight_status"] == "success"
    assert smoke["network_check_requested"] is True
    assert smoke["network_check_allowed"] is True
    assert smoke["safe_next_action"] == "refresh_landing_status_and_continue_manual_signoff"
    assert smoke["acceptance_blockers"] == []
    assert smoke["blocker_action_present"] is True
    assert smoke["blocker_safe_next_action"] == "manual_signoff_record_required"
    assert smoke["blocker_acceptance_blockers"] == ["[redacted-secret-like-command]"]
    assert smoke["missing_conditions"] == ["manual_signoff:not_completed"]
    assert smoke["public_production_direct_launch"] == "No-Go"
    assert smoke["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["operations_console_landing_smoke_reports"] == 1
    assert "sk-should-not-leak" not in text


def test_operations_summary_should_include_controlled_pilot_status_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    dirs = {
        "PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR": tmp_path / "bootstrap",
        "PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR": tmp_path / "bundle",
        "PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR": tmp_path / "final",
        "PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR": tmp_path / "closeout",
        "OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR": tmp_path / "ops_smoke",
        "CONTROLLED_PILOT_LAUNCH_PACKAGE_REPORT_DIR": tmp_path / "package",
        "CONTROLLED_PILOT_WINDOW_STATUS_REPORT_DIR": tmp_path / "window_status",
        "CONTROLLED_PILOT_STATUS_SUMMARY_REPORT_DIR": tmp_path / "status_summary",
        "CONTROLLED_PILOT_OPERATOR_PACKET_REPORT_DIR": tmp_path / "operator_packet",
        "BUSINESS_SYSTEM_READ_SMOKE_REPORT_DIR": tmp_path / "business_smoke",
        "BUSINESS_SYSTEM_PRODUCTION_READINESS_REPORT_DIR": tmp_path / "business_readiness",
    }
    for env_name, path in dirs.items():
        path.mkdir(parents=True)
        monkeypatch.setenv(env_name, str(path))

    (dirs["PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR"] / "001_production_pilot_bootstrap.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:00+00:00",
                "status": "partial",
                "operations_console_smoke_status": "success",
                "runtime_smoke_passed": True,
                "signoff_closeout_passed": True,
                "final_verification_passed": True,
                "pilot_evidence_bundle_passed": True,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR"] / "001_production_pilot_evidence_bundle.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:01+00:00",
                "status": "success",
                "controlled_pilot_ready": True,
                "final_verification_passed_count": 9,
                "final_verification_requirement_count": 9,
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
                "go_no_go": {"controlled_pilot": "Go", "public_production_direct_launch": "No-Go"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR"] / "001_production_landing_final_verification.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:02+00:00",
                "status": "success",
                "passed_count": 9,
                "requirement_count": 9,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR"] / "001_production_landing_signoff_closeout.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:03+00:00",
                "status": "success",
                "final_status": "success",
                "target_record_written": True,
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR"] / "001_operations_console_landing_smoke.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:04+00:00",
                "status": "success",
                "execute": True,
                "page_http_status": 200,
                "summary_http_status": 200,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["CONTROLLED_PILOT_LAUNCH_PACKAGE_REPORT_DIR"] / "001_controlled_pilot_launch_package.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:05+00:00",
                "status": "ready",
                "launch_package_ready": True,
                "controlled_pilot": "Go",
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["CONTROLLED_PILOT_WINDOW_STATUS_REPORT_DIR"] / "001_controlled_pilot_window_status.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:06+00:00",
                "status": "healthy",
                "missing_condition_count": 0,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["BUSINESS_SYSTEM_READ_SMOKE_REPORT_DIR"] / "001_business_system_read_smoke.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:07+00:00",
                "status": "skipped",
                "execute": False,
                "business_system_connected": False,
                "business_read_executed": False,
                "business_write_executed": False,
                "business_data_written": False,
                "env_profile": {"public_production_gap": True},
                "go_no_go": {"public_production_direct_launch": "No-Go"},
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dirs["BUSINESS_SYSTEM_PRODUCTION_READINESS_REPORT_DIR"] / "001_business_system_production_readiness.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:08+00:00",
                "status": "needs_input",
                "missing_condition_count": 2,
                "missing_conditions": [
                    "owner:operations_owner_missing",
                    "evidence:business_system_real_read_smoke_not_executed",
                ],
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    status = response.json()["observability"]["controlled_pilot_status_summary"]

    assert status["status"] == "partial"
    assert status["runbook_path"] == "scripts/controlled_pilot_status_summary.py"
    assert status["report_dir"] == str(dirs["CONTROLLED_PILOT_STATUS_SUMMARY_REPORT_DIR"])
    assert status["controlled_internal_pilot"] == "Manual-Review"
    assert status["public_production_direct_launch"] == "No-Go"
    assert status["secret_plaintext_output"] is False
    assert status["operations_console_smoke_execute"] is True
    assert status["blocking_reports"] == []
    assert status["public_production_gaps"] == [
        "business_system:production_readiness_not_ready",
        "business_system:public_production_gap",
        "business_system:real_read_only_smoke_not_executed",
    ]
    assert response.json()["observability"]["last_known_report_counts"]["controlled_pilot_status_summary_reports"] == 0


def test_operations_summary_should_include_controlled_pilot_operator_packet_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_operator_packet"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_OPERATOR_PACKET_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T09:40:00+00:00",
        "status": "ready",
        "controlled_internal_pilot": "Go",
        "public_production_direct_launch": "No-Go",
        "window": {"window_id": "controlled-pilot-2026-06-05"},
        "missing_condition_count": 0,
        "missing_conditions": [],
        "public_production_gap_count": 2,
        "public_production_gaps": [
            "business_system:public_production_gap",
            "business_system:real_read_only_smoke_not_executed",
        ],
        "business_system_read_smoke": {
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "auth_mode": "bearer",
        },
        "evidence_paths": {"controlled_pilot_status_summary": "docs/reports/status/latest.json"},
        "operator_commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_status_summary.py"],
        "pilot_roles": [{"role": "operations_owner"}],
        "rollback_required": True,
        "external_expansion_requires_new_manual_go_no_go": True,
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    (report_dir / "001_controlled_pilot_operator_packet.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    packet = data["observability"]["controlled_pilot_operator_packet"]

    assert packet["latest_report_present"] is True
    assert packet["status"] == "ready"
    assert packet["controlled_internal_pilot"] == "Go"
    assert packet["public_production_direct_launch"] == "No-Go"
    assert packet["window_id"] == "controlled-pilot-2026-06-05"
    assert packet["operator_command_count"] == 1
    assert packet["pilot_role_count"] == 1
    assert packet["rollback_required"] is True
    assert packet["external_expansion_requires_new_manual_go_no_go"] is True
    assert packet["public_production_gap_count"] == 2
    assert packet["public_production_gaps"] == [
        "business_system:public_production_gap",
        "business_system:real_read_only_smoke_not_executed",
    ]
    assert packet["business_system_read_smoke"]["auth_mode"] == "bearer"
    assert packet["business_system_read_smoke"]["business_read_executed"] is False
    assert packet["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_operator_packet_reports"] == 1


def test_operations_summary_should_include_controlled_pilot_console_verify_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_console_verify"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_CONSOLE_VERIFY_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T10:28:16+00:00",
        "status": "success",
        "controlled_internal_pilot": "Go",
        "public_production_direct_launch": "No-Go",
        "backend_url": "http://127.0.0.1:8000",
        "frontend_url": "http://127.0.0.1:3003/operations",
        "missing_condition_count": 0,
        "missing_conditions": [],
        "console_runtime": {"pid_file_present_after_verify": False},
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    (report_dir / "001_controlled_pilot_console_verify.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    verify = data["observability"]["controlled_pilot_console_verify"]

    assert verify["latest_report_present"] is True
    assert verify["status"] == "success"
    assert verify["controlled_internal_pilot"] == "Go"
    assert verify["public_production_direct_launch"] == "No-Go"
    assert verify["backend_url"] == "http://127.0.0.1:8000"
    assert verify["frontend_url"] == "http://127.0.0.1:3003/operations"
    assert verify["missing_condition_count"] == 0
    assert verify["pid_file_present_after_verify"] is False
    assert verify["secret_plaintext_output"] is False
    assert verify["real_llm_executed"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_console_verify_reports"] == 1


def test_operations_summary_should_include_controlled_pilot_console_preflight_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "controlled_pilot_console_preflight"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("CONTROLLED_PILOT_CONSOLE_PREFLIGHT_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T10:45:00+00:00",
        "status": "ready",
        "ready_for_local_verify": True,
        "recommended_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_verify.ps1",
        "backend_url": "http://127.0.0.1:8000",
        "frontend_url": "http://127.0.0.1:3003/operations",
        "blocking_condition_count": 0,
        "blocking_conditions": [],
        "latest_verify": {"status": "success", "controlled_internal_pilot": "Go"},
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    (report_dir / "001_controlled_pilot_console_preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    preflight = data["observability"]["controlled_pilot_console_preflight"]

    assert preflight["latest_report_present"] is True
    assert preflight["status"] == "ready"
    assert preflight["ready_for_local_verify"] is True
    assert preflight["recommended_command"].endswith("scripts\\controlled_pilot_console_verify.ps1")
    assert preflight["backend_url"] == "http://127.0.0.1:8000"
    assert preflight["frontend_url"] == "http://127.0.0.1:3003/operations"
    assert preflight["blocking_condition_count"] == 0
    assert preflight["latest_verify_status"] == "success"
    assert preflight["latest_verify_controlled_internal_pilot"] == "Go"
    assert preflight["public_production_direct_launch"] == "No-Go"
    assert preflight["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["controlled_pilot_console_preflight_reports"] == 1


def test_operations_summary_should_prefer_successful_executed_operations_console_smoke(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "operations_console_landing_smoke"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR", str(report_dir))
    (report_dir / "001_operations_console_landing_smoke.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:00:00+00:00",
                "status": "success",
                "execute": True,
                "page_http_status": 200,
                "summary_http_status": 200,
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (report_dir / "002_operations_console_landing_smoke.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T09:30:00+00:00",
                "status": "skipped",
                "execute": False,
                "missing_conditions": ["cli:--execute_not_requested"],
                "public_production_direct_launch": "No-Go",
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    smoke = response.json()["observability"]["operations_console_landing_smoke"]

    assert smoke["selection"] == "latest_successful_executed"
    assert smoke["status"] == "success"
    assert smoke["execute"] is True
    assert smoke["generated_at"] == "2026-06-05T09:00:00+00:00"


def test_operations_summary_should_include_real_production_environment_checklist_latest_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    report_dir = tmp_path / "docs" / "reports" / "real_production_environment_checklist"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_REPORT_DIR", str(report_dir))
    payload = {
        "generated_at": "2026-06-05T11:25:00+00:00",
        "status": "partial",
        "domain_count": 5,
        "domains": [
            {
                "domain_id": "postgres",
                "status": "partial",
                "owner": "数据库负责人",
                "phase": "Phase 25.3",
                "missing_conditions": ["postgres:database_not_connected"],
                "manual_signoff_required": True,
                "production_direct_launch": "No-Go",
            },
            {
                "domain_id": "business_system",
                "status": "partial",
                "owner": "业务系统集成负责人",
                "phase": "Phase 25.8",
                "missing_conditions": ["business_system:real_read_smoke_not_executed"],
                "manual_signoff_required": True,
                "production_direct_launch": "No-Go",
            },
        ],
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "business_data_written": False,
        "go_no_go": {"public_production_direct_launch": "No-Go"},
        "secret_plaintext_output": False,
    }
    (report_dir / "001_real_production_environment_checklist.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    checklist = data["observability"]["real_production_environment_checklist"]
    text = json.dumps(checklist, ensure_ascii=False)

    assert checklist["latest_report_present"] is True
    assert checklist["status"] == "partial"
    assert checklist["domain_count"] == 5
    assert checklist["domains"][0]["domain_id"] == "postgres"
    assert checklist["domains"][0]["missing_conditions"] == ["postgres:database_not_connected"]
    assert checklist["domains"][1]["missing_conditions"] == ["business_system:real_read_smoke_not_executed"]
    assert checklist["next_commands"]["postgres"].endswith("-Domains postgres")
    assert checklist["next_commands"]["business_system"].endswith("scripts\\business_system_read_smoke.ps1")
    assert checklist["public_production_direct_launch"] == "No-Go"
    assert checklist["secret_plaintext_output"] is False
    assert data["observability"]["last_known_report_counts"]["real_production_environment_checklist_reports"] == 1
    assert "should-not-leak" not in text
