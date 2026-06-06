from __future__ import annotations

import json
from pathlib import Path

from scripts import production_landing_action_pack as pack


def _write_json(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_landing_action_pack_lists_remaining_real_inputs(tmp_path: Path, monkeypatch) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_landing_xiaomi_llm_preflight",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    sources = {"launch_blockers": tmp_path / "reports" / "launch_blockers"}
    monkeypatch.setattr(pack, "SOURCE_DIRS", sources)
    templates = {
        "business_system_env_template": tmp_path / "business.env.template",
        "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
        "manual_signoff_record": tmp_path / "manual_signoff.json",
        "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
        "closure_evidence_template": tmp_path / "closure_evidence.json",
        "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
        "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
        "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
    }
    for path in templates.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(pack, "TEMPLATE_PATHS", templates)

    _write_json(
        reports["production_landing_input_readiness"],
        "001_production_landing_input_readiness.json",
        {"status": "partial", "ready_input_count": 0, "required_input_count": 3},
    )
    _write_json(
        reports["production_landing_xiaomi_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "skipped",
            "api_key_present": False,
            "execute_network_check": True,
            "real_llm_executed": False,
            "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
            "acceptance_blockers": [
                "missing_process_env:XIAOMI_LLM_API_KEY",
                "network_check_not_allowed_without_process_key",
            ],
            "preflight": {
                "network_check_requested": True,
                "network_check_allowed": False,
                "network_check_executed": False,
            },
        },
    )
    _write_json(
        reports["production_pilot_signoff"],
        "001_production_pilot_signoff.json",
        {
            "status": "partial",
            "manual_signoff_completed": False,
            "landing_status": {
                "real_infra_ready": False,
                "production_blockers": [
                    "business_system_read:not_executed",
                    "real_infra:postgres_redis_mcp_not_all_connected",
                    "manual_signoff:not_completed",
                ],
            },
        },
    )
    _write_json(
        reports["business_system_read_smoke"],
        "001_business_system_read_smoke.json",
        {"status": "skipped", "business_read_executed": False, "business_system_connected": False},
    )
    _write_json(
        reports["real_integration_staging_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "skipped",
            "preflight_summary": {
                "ready_domain_count": 0,
                "domain_count": 3,
                "ready_domains": [],
                "domains": [
                    {
                        "domain_id": "postgres",
                        "ready_for_execute": False,
                        "missing_count": 3,
                        "required_env": [
                            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
                            "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                            "DATABASE_URL=<secret-managed-url>",
                        ],
                    }
                ],
            },
        },
    )
    _write_json(
        reports["manual_signoff_package"],
        "001_manual_signoff_package.json",
        {"status": "partial", "manual_signoff_completed": False, "manual_signoff_record_present": False},
    )
    _write_json(
        reports["manual_signoff_evidence_ack_status"],
        "001_manual_signoff_evidence_ack_status.json",
        {
            "status": "partial",
            "recommended_accept_count": 3,
            "item_count": 4,
            "items": [
                {
                    "item": "real_llm_preflight",
                    "source_status": "skipped",
                    "recommended_accept": False,
                    "missing_conditions": ["real_llm_preflight:status_not_success"],
                }
            ],
        },
    )
    _write_json(reports["closure_evidence_index"], "001_closure_evidence_index.json", {"status": "partial", "report_count": 1})
    _write_json(sources["launch_blockers"], "001_launch_blocker_register.json", {"status": "partial", "blocker_count": 13})
    _write_json(
        reports["launch_blocker_closure"],
        "001_launch_blocker_closure_workflow.json",
        {"status": "partial", "closure_item_count": 13, "evidence_incomplete_count": 13},
    )

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    input_ids = {item["input_id"] for item in payload["required_inputs"]}

    assert summary["status"] == "partial"
    assert input_ids == {
        "business_system_read_only_credentials",
        "launch_blocker_closure_evidence",
        "real_infra_current_round_acceptance",
        "manual_signoff_record",
    }
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert all(item["exists"] for item in payload["templates"].values())
    assert payload["input_readiness"]["status"] == "partial"
    assert payload["operator_runbook_path"] == "docs/production_landing_operator_runbook_v47.md"
    assert payload["recommended_commands"][0] == "python scripts/production_landing_status.py"
    assert payload["recommended_commands"][1] == "python scripts/production_landing_env_init.py"
    assert payload["recommended_commands"][2] == "python scripts/production_landing_local_infra_bootstrap.py"
    assert payload["recommended_commands"][3] == "python scripts/production_landing_xiaomi_llm_bootstrap.py"
    assert (
        payload["recommended_commands"][4]
        == "python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight"
    )
    assert (
        payload["recommended_commands"][5]
        == "python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check"
    )
    assert payload["recommended_commands"][6] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
    assert payload["recommended_commands"][7] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_landing_resume.ps1"
    assert "python scripts/production_landing_local_mcp_bootstrap.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_local_business_bootstrap.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_template.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_check.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_execution_gate.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_status.py" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_runner.py --action env-check" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_runner.py --action staging-smoke" in payload["recommended_commands"]
    assert "python scripts/production_landing_env_runner.py --action business-smoke" in payload["recommended_commands"]
    assert any(command.startswith("python scripts/production_landing_closure_evidence_draft.py") for command in payload["recommended_commands"])
    assert "<latest-launch-blockers.json>" not in "\n".join(payload["recommended_commands"])
    assert "<latest-closure-index.json>" not in "\n".join(payload["recommended_commands"])
    assert payload["resolved_paths"]["latest_launch_blockers"].endswith("001_launch_blocker_register.json")
    assert payload["resolved_paths"]["latest_closure_index"].endswith("001_closure_evidence_index.json")
    assert (
        "python scripts/production_landing_input_readiness.py "
        f"--closure-evidence {payload['resolved_paths']['closure_evidence_draft']}"
    ) in payload["recommended_commands"]
    business_input = next(item for item in payload["required_inputs"] if item["input_id"] == "business_system_read_only_credentials")
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>" in business_input["required_env"]
    assert "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>" in business_input["required_env"]
    closure_input = next(item for item in payload["required_inputs"] if item["input_id"] == "launch_blocker_closure_evidence")
    assert closure_input["draft"] == str(templates["closure_evidence_draft"])
    assert "closure_evidence.draft.json" in closure_input["command_after_fill"]
    infra_input = next(item for item in payload["required_inputs"] if item["input_id"] == "real_infra_current_round_acceptance")
    assert infra_input["must_use_current_round_evidence"] is True
    assert infra_input["process_env_only_llm_preflight_command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
    )
    assert infra_input["xiaomi_llm_preflight"]["api_key_present"] is False
    assert infra_input["xiaomi_llm_preflight"]["network_check_requested"] is True
    assert infra_input["xiaomi_llm_preflight"]["network_check_allowed"] is False
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in infra_input["xiaomi_llm_acceptance_blockers"]
    assert infra_input["xiaomi_llm_safe_next_action"] == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    assert infra_input["current_blockers"] == ["real_infra:postgres_redis_mcp_not_all_connected"]
    assert infra_input["preflight_summary"]["domain_count"] == 3
    assert infra_input["preflight_domains"][0]["domain_id"] == "postgres"
    assert "DATABASE_URL=<secret-managed-url>" in infra_input["preflight_domains"][0]["required_env"]
    assert infra_input["template"].endswith("production_landing.staging.env.template")
    assert infra_input["local_env_path"].endswith("production_landing.staging.env")
    assert "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true" in infra_input["required_env"]
    assert "REAL_LLM_MODEL=mimo-v2.5-pro" in infra_input["required_env"]
    assert "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1" in infra_input["required_env"]
    assert "XIAOMI_LLM_API_KEY=<secret-managed-token>" in infra_input["required_env"]
    assert "DATABASE_URL=<secret-managed-url>" in infra_input["required_env"]
    assert "scripts\\xiaomi_llm_preflight.ps1" in infra_input["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains postgres" in infra_input["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains redis" in infra_input["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in infra_input["command_after_fill"]
    commands = "\n".join(payload["recommended_commands"])
    assert "scripts\\business_system_read_smoke.ps1" in commands
    assert "scripts\\business_system_landing_resume.ps1 -UseExistingEnv" in commands
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains postgres" in commands
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains redis" in commands
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in commands
    assert "python scripts/production_landing_text_quality_check.py" in payload["recommended_commands"]
    assert "python scripts/manual_signoff_evidence_ack_status.py" in payload["recommended_commands"]
    assert "python scripts/manual_signoff_record_draft.py" in payload["recommended_commands"]
    assert any("manual_signoff_record_promote.py" in command for command in payload["recommended_commands"])
    assert "python scripts/manual_signoff_record_validator.py" in payload["recommended_commands"]
    manual_input = next(item for item in payload["required_inputs"] if item["input_id"] == "manual_signoff_record")
    assert manual_input["filled_record"] == str(templates["manual_signoff_record"])
    assert manual_input["draft"] == str(templates["manual_signoff_record_draft"])
    assert manual_input["command_after_fill"].replace("\\", "/").endswith(
        str(templates["manual_signoff_record"]).replace("\\", "/")
    )
    assert "manual_signoff_record_promote.py" in manual_input["promote_command_after_manual_fill"]
    assert payload["resolved_paths"]["manual_signoff_record_draft"] in manual_input["promote_command_after_manual_fill"]
    assert payload["resolved_paths"]["manual_signoff_record"] in manual_input["promote_command_after_manual_fill"]
    assert manual_input["evidence_ack_status"]["recommended_accept_count"] == 3
    assert manual_input["evidence_ack_status"]["item_count"] == 4
    assert manual_input["evidence_ack_report"].endswith("001_manual_signoff_evidence_ack_status.json")
    assert manual_input["blocking_evidence_items"][0]["item"] == "real_llm_preflight"
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in manual_input["blocking_evidence_items"][0]["acceptance_blockers"]
    assert (
        manual_input["blocking_evidence_items"][0]["safe_next_action"]
        == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    )
    assert manual_input["blocking_evidence_items"][0]["safe_commands"][0] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_landing_resume.ps1"
    )
    assert any("production_landing_signoff_closeout.py" in command for command in payload["recommended_commands"])
    assert "powershell -ExecutionPolicy Bypass -File scripts/production_landing_signoff_closeout.ps1" in payload[
        "recommended_commands"
    ]
    assert all(
        command.startswith("python ")
        or command
        in {
                "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1",
                "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1",
                "powershell -ExecutionPolicy Bypass -File scripts/production_landing_signoff_closeout.ps1",
                "powershell -ExecutionPolicy Bypass -File scripts/manual_signoff_record_fill.ps1",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_landing_resume.ps1",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_landing_resume.ps1 -UseExistingEnv",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp -McpServerCommand <approved-command> -McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>",
            }
            for command in payload["recommended_commands"]
        )


def test_production_landing_action_pack_success_when_required_inputs_closed(tmp_path: Path, monkeypatch) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_landing_xiaomi_llm_preflight",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    sources = {"launch_blockers": tmp_path / "reports" / "launch_blockers"}
    monkeypatch.setattr(pack, "SOURCE_DIRS", sources)
    monkeypatch.setattr(
        pack,
        "TEMPLATE_PATHS",
        {
            "business_system_env_template": tmp_path / "business.env.template",
            "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
            "manual_signoff_record": tmp_path / "manual_signoff.json",
            "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
            "closure_evidence_template": tmp_path / "closure_evidence.json",
            "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
            "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
            "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
        },
    )

    _write_json(
        reports["production_landing_input_readiness"],
        "001_production_landing_input_readiness.json",
        {"status": "success", "ready_input_count": 3, "required_input_count": 3},
    )
    _write_json(
        reports["production_landing_xiaomi_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {"status": "success", "api_key_present": True, "real_llm_executed": True},
    )
    _write_json(
        reports["production_pilot_signoff"],
        "001_production_pilot_signoff.json",
        {"status": "partial", "manual_signoff_completed": True, "landing_status": {"real_infra_ready": True}},
    )
    _write_json(
        reports["business_system_read_smoke"],
        "001_business_system_read_smoke.json",
        {"status": "success", "business_read_executed": True, "business_system_connected": True},
    )
    _write_json(
        reports["manual_signoff_package"],
        "001_manual_signoff_package.json",
        {"status": "success", "manual_signoff_completed": True, "manual_signoff_record_present": True},
    )
    _write_json(
        reports["manual_signoff_evidence_ack_status"],
        "001_manual_signoff_evidence_ack_status.json",
        {"status": "success", "recommended_accept_count": 4, "item_count": 4},
    )
    _write_json(reports["closure_evidence_index"], "001_closure_evidence_index.json", {"status": "partial", "report_count": 1})
    _write_json(sources["launch_blockers"], "001_launch_blocker_register.json", {"status": "partial", "blocker_count": 0})
    _write_json(
        reports["launch_blocker_closure"],
        "001_launch_blocker_closure_workflow.json",
        {"status": "partial", "closure_item_count": 13, "evidence_incomplete_count": 0},
    )

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["required_inputs"] == []
    assert payload["input_readiness"]["status"] == "success"
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_action_pack_accepts_validated_formal_signoff_when_legacy_summary_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_landing_xiaomi_llm_preflight",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "manual_signoff_record_validation",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    monkeypatch.setattr(pack, "SOURCE_DIRS", {"launch_blockers": tmp_path / "reports" / "launch_blockers"})
    monkeypatch.setattr(
        pack,
        "TEMPLATE_PATHS",
        {
            "business_system_env_template": tmp_path / "business.env.template",
            "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
            "manual_signoff_record": tmp_path / "manual_signoff.json",
            "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
            "closure_evidence_template": tmp_path / "closure_evidence.json",
            "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
            "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
            "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
        },
    )
    for path in pack.TEMPLATE_PATHS.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")

    _write_json(reports["production_landing_input_readiness"], "001_production_landing_input_readiness.json", {"status": "success"})
    _write_json(
        reports["production_landing_xiaomi_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {"status": "success", "api_key_present": True, "real_llm_executed": True},
    )
    _write_json(
        reports["production_pilot_signoff"],
        "001_production_pilot_signoff.json",
        {"status": "partial", "manual_signoff_completed": False, "landing_status": {"real_infra_ready": True}},
    )
    _write_json(
        reports["business_system_read_smoke"],
        "001_business_system_read_smoke.json",
        {"status": "success", "business_read_executed": True, "business_system_connected": True},
    )
    _write_json(
        reports["manual_signoff_package"],
        "001_manual_signoff_package.json",
        {"status": "partial", "manual_signoff_completed": False, "manual_signoff_record_present": False},
    )
    _write_json(
        reports["manual_signoff_evidence_ack_status"],
        "001_manual_signoff_evidence_ack_status.json",
        {"status": "success", "recommended_accept_count": 4, "item_count": 4},
    )
    _write_json(
        reports["manual_signoff_record_validation"],
        "001_manual_signoff_record_validation.json",
        {
            "status": "success",
            "manual_signoff_completed": True,
            "signoff_record_present": True,
            "decision": "Go",
            "missing_conditions": [],
            "missing_condition_count": 0,
        },
    )
    _write_json(reports["closure_evidence_index"], "001_closure_evidence_index.json", {"status": "partial", "report_count": 1})
    _write_json(reports["launch_blocker_closure"], "001_launch_blocker_closure_workflow.json", {"status": "partial", "evidence_incomplete_count": 0})

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["required_input_count"] == 0
    assert payload["required_inputs"] == []


def test_production_landing_action_pack_prefers_latest_generated_at(tmp_path: Path, monkeypatch) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_landing_xiaomi_llm_preflight",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    monkeypatch.setattr(pack, "SOURCE_DIRS", {"launch_blockers": tmp_path / "reports" / "launch_blockers"})
    monkeypatch.setattr(
        pack,
        "TEMPLATE_PATHS",
        {
            "business_system_env_template": tmp_path / "business.env.template",
            "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
            "manual_signoff_record": tmp_path / "manual_signoff.json",
            "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
            "closure_evidence_template": tmp_path / "closure_evidence.json",
            "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
            "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
            "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
        },
    )
    for path in pack.TEMPLATE_PATHS.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")

    _write_json(reports["production_landing_input_readiness"], "999_production_landing_input_readiness.json", {"generated_at": "2026-06-04T20:00:00+00:00", "status": "success"})
    _write_json(reports["production_landing_input_readiness"], "001_production_landing_input_readiness.json", {"generated_at": "2026-06-04T20:30:00+00:00", "status": "partial"})
    _write_json(reports["production_landing_xiaomi_llm_preflight"], "001_production_landing_xiaomi_llm_preflight.json", {"status": "success", "api_key_present": True, "real_llm_executed": True})
    _write_json(reports["production_pilot_signoff"], "001_production_pilot_signoff.json", {"status": "partial", "manual_signoff_completed": True, "landing_status": {"real_infra_ready": True}})
    _write_json(reports["business_system_read_smoke"], "001_business_system_read_smoke.json", {"status": "success", "business_read_executed": True, "business_system_connected": True})
    _write_json(reports["manual_signoff_package"], "001_manual_signoff_package.json", {"status": "success", "manual_signoff_completed": True, "manual_signoff_record_present": True})
    _write_json(reports["manual_signoff_evidence_ack_status"], "001_manual_signoff_evidence_ack_status.json", {"status": "success", "recommended_accept_count": 4, "item_count": 4})
    _write_json(reports["closure_evidence_index"], "001_closure_evidence_index.json", {"status": "partial", "report_count": 1})
    _write_json(reports["launch_blocker_closure"], "001_launch_blocker_closure_workflow.json", {"status": "partial", "closure_item_count": 13, "evidence_incomplete_count": 0})

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["input_readiness"]["summary"]["generated_at"] == "2026-06-04T20:30:00+00:00"


def test_production_landing_action_pack_ignores_closure_draft_as_workflow_report(tmp_path: Path, monkeypatch) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_landing_xiaomi_llm_preflight",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    sources = {"launch_blockers": tmp_path / "reports" / "launch_blockers"}
    monkeypatch.setattr(pack, "SOURCE_DIRS", sources)
    monkeypatch.setattr(
        pack,
        "TEMPLATE_PATHS",
        {
            "business_system_env_template": tmp_path / "business.env.template",
            "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
            "manual_signoff_record": tmp_path / "manual_signoff.json",
            "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
            "closure_evidence_template": tmp_path / "closure_evidence.json",
            "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
            "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
            "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
        },
    )
    _write_json(reports["production_landing_input_readiness"], "001_production_landing_input_readiness.json", {"status": "partial"})
    _write_json(
        reports["production_landing_xiaomi_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {"status": "skipped", "api_key_present": False, "real_llm_executed": False},
    )
    _write_json(reports["production_pilot_signoff"], "001_production_pilot_signoff.json", {"status": "partial", "manual_signoff_completed": False})
    _write_json(reports["business_system_read_smoke"], "001_business_system_read_smoke.json", {"status": "skipped", "business_read_executed": False})
    _write_json(reports["manual_signoff_package"], "001_manual_signoff_package.json", {"status": "partial", "manual_signoff_completed": False})
    _write_json(reports["manual_signoff_evidence_ack_status"], "001_manual_signoff_evidence_ack_status.json", {"status": "partial", "recommended_accept_count": 3, "item_count": 4})
    _write_json(reports["closure_evidence_index"], "001_closure_evidence_index.json", {"status": "partial"})
    _write_json(
        reports["launch_blocker_closure"],
        "closure_evidence.draft.json",
        {"status": "partial", "closure_item_count": 13, "draft_only": True},
    )

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert payload["reports"]["launch_blocker_closure"]["present"] is False
    input_ids = {item["input_id"] for item in payload["required_inputs"]}
    assert "launch_blocker_closure_evidence" in input_ids
    assert "real_infra_current_round_acceptance" in input_ids


def test_production_landing_action_pack_keeps_placeholders_when_source_reports_missing(
    tmp_path: Path, monkeypatch
) -> None:
    reports = {
        key: tmp_path / "reports" / key
        for key in [
            "production_landing_input_readiness",
            "production_pilot_signoff",
            "business_system_read_smoke",
            "real_integration_staging_smoke",
            "manual_signoff_package",
            "manual_signoff_evidence_ack_status",
            "closure_evidence_index",
            "launch_blocker_closure",
        ]
    }
    monkeypatch.setattr(pack, "REPORT_DIRS", reports)
    monkeypatch.setattr(pack, "SOURCE_DIRS", {"launch_blockers": tmp_path / "reports" / "missing_launch_blockers"})
    monkeypatch.setattr(
        pack,
        "TEMPLATE_PATHS",
        {
            "business_system_env_template": tmp_path / "business.env.template",
            "manual_signoff_record_template": tmp_path / "manual_signoff.template.json",
            "manual_signoff_record": tmp_path / "manual_signoff.json",
            "manual_signoff_record_draft": tmp_path / "manual_signoff.draft.json",
            "closure_evidence_template": tmp_path / "closure_evidence.json",
            "closure_evidence_draft": tmp_path / "closure_evidence.draft.json",
            "production_landing_env_template": tmp_path / "local" / "production_landing.staging.env.template",
            "production_landing_env_file": tmp_path / "local" / "production_landing.staging.env",
        },
    )
    _write_json(reports["production_landing_input_readiness"], "001_production_landing_input_readiness.json", {"status": "partial"})
    _write_json(reports["production_pilot_signoff"], "001_production_pilot_signoff.json", {"status": "partial", "manual_signoff_completed": False})
    _write_json(reports["business_system_read_smoke"], "001_business_system_read_smoke.json", {"status": "skipped", "business_read_executed": False})
    _write_json(reports["manual_signoff_package"], "001_manual_signoff_package.json", {"status": "partial", "manual_signoff_completed": False})
    _write_json(reports["manual_signoff_evidence_ack_status"], "001_manual_signoff_evidence_ack_status.json", {"status": "partial", "recommended_accept_count": 3, "item_count": 4})
    _write_json(
        reports["launch_blocker_closure"],
        "001_launch_blocker_closure_workflow.json",
        {"status": "partial", "closure_item_count": 13, "evidence_incomplete_count": 13},
    )

    summary = pack.build_production_landing_action_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    commands = "\n".join(payload["recommended_commands"])

    assert payload["resolved_paths"]["latest_launch_blockers"] == "<latest-launch-blockers.json>"
    assert payload["resolved_paths"]["latest_closure_index"] == "<latest-closure-index.json>"
    assert "<latest-launch-blockers.json>" in commands
    assert "<latest-closure-index.json>" in commands
    assert "real_infra_current_round_acceptance" in {item["input_id"] for item in payload["required_inputs"]}
