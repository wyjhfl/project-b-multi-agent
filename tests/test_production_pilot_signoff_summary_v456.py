from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.production_pilot_signoff_summary import build_production_pilot_signoff_summary


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _make_source_dirs(root: Path) -> dict[str, Path]:
    mapping = {
        "production_runtime_smoke": root / "production_runtime_smoke",
        "frontend_production_build": root / "frontend_production_build",
        "production_pilot_bootstrap": root / "production_pilot_bootstrap",
        "real_production_environment_checklist": root / "real_production_environment_checklist",
        "real_integration_staging_smoke": root / "real_integration_staging_smoke",
        "business_system_read_smoke": root / "business_system_read_smoke",
        "manual_signoff_package": root / "manual_signoff_package",
    }
    for directory in mapping.values():
        directory.mkdir(parents=True, exist_ok=True)
    return mapping


def _write_json(directory: Path, name: str, payload: dict) -> None:
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_ready_sources(dirs: dict[str, Path]) -> None:
    _write_json(
        dirs["production_runtime_smoke"],
        "001.json",
        {
            "status": "success",
            "endpoint_checks": [{"path": "/health"}, {"path": "/operations/summary"}, {"path": "/deployment/check"}],
            "operations_contract": {
                "status": "success",
                "frontend_build_status": "success",
                "frontend_build_executed": True,
                "business_system_connected": False,
            },
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["frontend_production_build"],
        "001.json",
        {
            "status": "success",
            "build_executed": True,
            "return_code": 0,
            "frontend_dir_present": True,
            "package_json_present": True,
            "node_modules_present": True,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_pilot_bootstrap"],
        "001.json",
        {
            "status": "skipped",
            "evidence_count": 13,
            "runtime_smoke_passed": True,
            "frontend_build_passed": True,
            "auth_rbac_acceptance_passed": True,
            "business_system_connected": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["real_production_environment_checklist"],
        "001.json",
        {
            "status": "partial",
            "domain_count": 4,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["real_integration_staging_smoke"],
        "001.json",
        {
            "status": "success",
            "domain_count": 2,
            "real_llm_executed": False,
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": False,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_read_smoke"],
        "001.json",
        {
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["manual_signoff_package"],
        "001.json",
        {
            "status": "partial",
            "manual_signoff_required": True,
            "manual_signoff_completed": False,
            "manual_signoff_record_present": False,
            "manual_signoff_roles": [],
            "manual_signoff_decision": "",
            "manual_signoff_blockers": ["manual_signoff_record:input_not_provided"],
            "auto_signed": False,
            "auto_approved": False,
            "secret_plaintext_output": False,
        },
    )


def test_production_pilot_signoff_summary_skips_without_sources(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["manual_signoff_required"] is True
    assert payload["manual_signoff_completed"] is False
    assert payload["auto_signed"] is False
    assert payload["auto_approved"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert "runtime_smoke:not_success" in payload["missing_conditions"]
    assert "frontend_build:not_success_or_not_executed" in payload["missing_conditions"]


def test_production_pilot_signoff_summary_reaches_manual_review_with_required_local_evidence(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    items = {item["item_id"]: item for item in payload["readiness_items"]}

    assert payload["status"] == "partial"
    assert payload["go_no_go"]["recommendation"] == "Manual-Review"
    assert payload["go_no_go"]["production_pilot"] == "Manual-Review"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert items["runtime_smoke_ready"]["status"] == "success"
    assert items["frontend_build_ready"]["status"] == "success"
    assert items["auth_rbac_ready"]["status"] == "success"
    assert items["business_system_read_ready"]["status"] == "skipped"
    assert payload["landing_status"]["required_local_ready"] is True
    assert payload["landing_status"]["controlled_pilot_manual_review_ready"] is True
    assert payload["landing_status"]["enterprise_landing_state"] == "controlled-pilot-manual-review"
    assert payload["landing_status"]["business_system_read_ready"] is False
    assert payload["landing_status"]["real_infra_ready"] is False
    assert payload["landing_status"]["database_connected"] is True
    assert payload["landing_status"]["redis_connected"] is True
    assert payload["landing_status"]["external_mcp_connected"] is False
    assert "business_system_read:not_executed" in payload["landing_status"]["production_blockers"]
    assert "real_infra:postgres_redis_mcp_not_all_connected" in payload["landing_status"]["production_blockers"]
    assert payload["landing_status"]["public_production_direct_launch"] == "No-Go"
    assert "business_system_read:not_executed" in payload["missing_conditions"]


def test_production_pilot_signoff_summary_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["production_runtime_smoke"],
        "999.json",
        {"status": "success", "note": "token=sk-signoff-secret", "secret_plaintext_output": False},
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "sk-signoff-secret" not in merged
    assert "production_runtime_smoke:secret_like_text_detected" in payload["missing_conditions"]


def test_production_pilot_signoff_summary_allows_secret_managed_placeholders(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["business_system_read_smoke"],
        "999.json",
        {
            "status": "skipped",
            "execute": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "missing_conditions": ["cli:--execute_not_requested"],
            "secret_plaintext_output": False,
            "env_profile": {
                "required_env": [
                    "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
                    "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                ]
            },
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert "business_system_read_smoke:secret_like_text_detected" not in payload["missing_conditions"]
    assert "business_system_read:not_executed" in payload["missing_conditions"]


def test_production_pilot_signoff_summary_markdown_is_readable_chinese(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "# 生产试点人工签核摘要" in markdown
    assert "controlled_pilot_manual_review_ready: True" in markdown
    assert "## Production Blockers" in markdown
    assert "鐢熶骇" not in markdown


def test_production_pilot_signoff_summary_prefers_successful_frontend_build_over_skipped(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["frontend_production_build"],
        "999_skipped.json",
        {
            "status": "skipped",
            "build_executed": False,
            "return_code": None,
            "missing_conditions": ["cli:--execute_not_requested"],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    frontend = payload["sources"]["frontend_production_build"]

    assert payload["status"] == "partial"
    assert frontend["status"] == "success"
    assert frontend["summary"]["build_executed"] is True


def test_production_pilot_signoff_summary_uses_latest_staging_smoke_for_current_landing_state(
    tmp_path: Path,
) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["real_integration_staging_smoke"],
        "999_skipped.json",
        {
            "status": "skipped",
            "domain_count": 4,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED"],
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    staging = payload["sources"]["real_integration_staging_smoke"]

    assert staging["status"] == "skipped"
    assert staging["summary"]["database_connected"] is False
    assert staging["summary"]["redis_connected"] is False
    assert staging["summary"]["aggregated_infra_flags"]["database_connected"] is True
    assert staging["summary"]["aggregated_infra_flags"]["redis_connected"] is True
    assert payload["landing_status"]["database_connected"] is False
    assert payload["landing_status"]["redis_connected"] is False
    assert payload["landing_status"]["external_mcp_connected"] is False
    assert payload["landing_status"]["real_infra_ready"] is False


def test_production_pilot_signoff_summary_prefers_generated_at_over_mtime_for_staging_current(
    tmp_path: Path,
) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    current = dirs["real_integration_staging_smoke"] / "100_current_ready.json"
    stale = dirs["real_integration_staging_smoke"] / "999_stale_skipped.json"
    _write_json(
        dirs["real_integration_staging_smoke"],
        current.name,
        {
            "generated_at": "2026-06-05T10:00:00+00:00",
            "status": "success",
            "domain_count": 3,
            "real_llm_executed": False,
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["real_integration_staging_smoke"],
        stale.name,
        {
            "generated_at": "2026-06-05T09:00:00+00:00",
            "status": "skipped",
            "domain_count": 3,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    os.utime(current, (1, 1))
    os.utime(stale, (2, 2))

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    staging = payload["sources"]["real_integration_staging_smoke"]

    assert staging["latest_json_path"] == str(current)
    assert staging["status"] == "success"
    assert payload["landing_status"]["real_infra_ready"] is True


def test_production_pilot_signoff_summary_accepts_single_current_staging_report_with_all_infra_domains(
    tmp_path: Path,
) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["real_integration_staging_smoke"],
        "999_all_infra.json",
        {
            "status": "success",
            "domain_count": 3,
            "real_llm_executed": False,
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    staging = payload["sources"]["real_integration_staging_smoke"]

    assert staging["summary"]["database_connected"] is True
    assert staging["summary"]["redis_connected"] is True
    assert staging["summary"]["external_mcp_connected"] is True
    assert payload["landing_status"]["database_connected"] is True
    assert payload["landing_status"]["redis_connected"] is True
    assert payload["landing_status"]["external_mcp_connected"] is True
    assert payload["landing_status"]["real_infra_ready"] is True
    assert "real_infra:postgres_redis_mcp_not_all_connected" not in payload["landing_status"]["production_blockers"]


def test_production_pilot_signoff_summary_keeps_historical_infra_aggregation_diagnostic_only(
    tmp_path: Path,
) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["real_integration_staging_smoke"],
        "999_external_mcp_later.json",
        {
            "status": "success",
            "domain_count": 1,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)
    staging = payload["sources"]["real_integration_staging_smoke"]

    assert staging["summary"]["database_connected"] is False
    assert staging["summary"]["redis_connected"] is False
    assert staging["summary"]["external_mcp_connected"] is True
    assert staging["summary"]["aggregated_infra_flags"]["database_connected"] is True
    assert staging["summary"]["aggregated_infra_flags"]["redis_connected"] is True
    assert staging["summary"]["aggregated_infra_flags"]["external_mcp_connected"] is True
    assert payload["landing_status"]["database_connected"] is False
    assert payload["landing_status"]["redis_connected"] is False
    assert payload["landing_status"]["external_mcp_connected"] is True
    assert payload["landing_status"]["real_infra_ready"] is False
    assert "real_infra:postgres_redis_mcp_not_all_connected" in payload["landing_status"]["production_blockers"]


def test_production_pilot_signoff_summary_consumes_completed_manual_signoff_package(tmp_path: Path) -> None:
    dirs = _make_source_dirs(tmp_path / "sources")
    _write_ready_sources(dirs)
    _write_json(
        dirs["manual_signoff_package"],
        "999_completed.json",
        {
            "status": "success",
            "manual_signoff_required": True,
            "manual_signoff_completed": True,
            "manual_signoff_record_present": True,
            "manual_signoff_roles": [
                "release_manager",
                "security_reviewer",
                "business_owner",
                "operations_owner",
            ],
            "manual_signoff_decision": "Go",
            "manual_signoff_blockers": [],
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
                }
            ],
            "auto_signed": False,
            "auto_approved": False,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_pilot_signoff_summary(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _read_payload(summary)

    assert payload["manual_signoff_completed"] is True
    assert payload["landing_status"]["manual_signoff_ready"] is True
    assert payload["landing_status"]["manual_signoff_record_present"] is True
    assert payload["landing_status"]["manual_signoff_decision"] == "Go"
    assert payload["closure_evidence_summary"]["latest_report"] == "docs/reports/launch_blocker_closure/latest.json"
    assert payload["closure_evidence_summary"]["closure_item_count"] == 13
    assert payload["closure_evidence_summary"]["evidence_incomplete_count"] == 13
    assert payload["landing_status"]["closure_evidence_summary"]["closure_item_count"] == 13
    assert "manual_signoff:not_completed" not in payload["landing_status"]["production_blockers"]
    assert "business_system_read:not_executed" in payload["landing_status"]["production_blockers"]
