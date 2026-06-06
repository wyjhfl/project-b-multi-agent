from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.production_pilot_bootstrap import (
    _derive_status,
    _latest_successful_real_llm_evidence,
    build_production_pilot_bootstrap,
)


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_pilot_bootstrap_generates_local_report(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)

    assert summary["local_service_status"] == "success"
    assert payload["status"] in {"skipped", "partial"}
    assert payload["execute_real_smoke"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["secret_plaintext_output"] is False
    assert Path(summary["markdown_path"]).exists()


def test_production_pilot_bootstrap_includes_actionable_next_commands(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(output_dir=tmp_path / "out", domains=["real_llm"])
    payload = _read_payload(summary)

    assert "local_pilot" in payload["next_commands"]
    assert "real_llm" in payload["next_commands"]
    assert "frontend" in payload["next_commands"]
    assert any("--execute-real-smoke --domains real_llm" in item for item in payload["next_commands"]["real_llm"])
    assert any("--execute-frontend-build-check" in item for item in payload["next_commands"]["frontend"])
    assert any("--include-runtime-smoke" in item for item in payload["next_commands"]["runtime_smoke"])
    assert payload["requested_domains"] == ["real_llm"]
    assert payload["evidence_count"] == 17


def test_production_pilot_bootstrap_execute_request_remains_opt_in_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", raising=False)
    monkeypatch.delenv("REAL_LLM_STAGING_SMOKE_EXECUTE", raising=False)

    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        execute_real_smoke=True,
        domains=["real_llm"],
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    staging_smoke = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert payload["execute_real_smoke"] is True
    assert staging_smoke["status"] == "blocked"
    assert payload["real_llm_executed"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_production_pilot_bootstrap_execute_status_prioritizes_staging_smoke_success() -> None:
    status = _derive_status(
        {"status": "success"},
        [
            {"evidence_id": "real_integration_staging_smoke", "status": "success"},
            {"evidence_id": "real_integration_staging_gate", "status": "blocked"},
            {"evidence_id": "real_integration_gap_register", "status": "blocked"},
        ],
        execute_real_smoke=True,
    )

    assert status == "partial"


def test_production_pilot_bootstrap_includes_migration_drill_evidence(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)

    migration = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_migration_drill")

    assert migration["status"] == "skipped"
    assert payload["migration_executed"] is False


def test_production_pilot_bootstrap_includes_business_system_safety_evidence(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    business = next(
        item for item in payload["evidence_runs"] if item["evidence_id"] == "business_system_integration_safety"
    )

    assert business["business_system_connected"] is False
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False


def test_production_pilot_bootstrap_includes_business_read_smoke_evidence(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "business_system_read_smoke")

    assert smoke["business_system_connected"] is False
    assert smoke["business_read_executed"] is False
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False


def test_production_pilot_bootstrap_includes_auth_rbac_acceptance_evidence(tmp_path: Path) -> None:
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        execute_auth_rbac_acceptance=True,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    auth = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_auth_rbac_acceptance")

    assert auth["status"] == "success"
    assert payload["auth_rbac_acceptance_passed"] is True
    assert payload["auth_enabled"] is True
    assert payload["rbac_enabled"] is True
    assert payload["jwt_token_issued"] is True
    assert payload["secret_plaintext_output"] is False


def test_production_pilot_bootstrap_includes_frontend_build_evidence(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Compiled successfully", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        execute_frontend_build_check=True,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    frontend = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "frontend_production_build")

    assert frontend["status"] == "success"
    assert frontend["build_executed"] is True
    assert frontend["return_code"] == 0
    assert payload["execute_frontend_build_check"] is True
    assert payload["frontend_build_passed"] is True
    assert payload["frontend_build_executed"] is True
    assert payload["frontend_build_return_code"] == 0


def test_production_pilot_bootstrap_includes_runtime_smoke_evidence(tmp_path: Path, monkeypatch) -> None:
    from scripts import production_pilot_bootstrap as module

    monkeypatch.setattr(
        module,
        "build_production_runtime_smoke",
        lambda: {
            "status": "success",
            "mode": "in_process_runtime_smoke",
            "endpoint_check_count": 3,
            "operations_contract_status": "success",
            "frontend_build_status": "success",
            "frontend_build_executed": True,
            "bootstrap_status": "partial",
            "business_system_connected": False,
            "secret_plaintext_output": False,
            "json_path": "docs/reports/production_runtime_smoke/demo.json",
        },
    )
    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        include_runtime_smoke=True,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    runtime = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_runtime_smoke")

    assert runtime["status"] == "success"
    assert payload["include_runtime_smoke"] is True
    assert payload["runtime_smoke_passed"] is True
    assert payload["runtime_smoke_endpoint_check_count"] == 3


def test_production_pilot_bootstrap_includes_final_closeout_evidence(tmp_path: Path, monkeypatch) -> None:
    from scripts import production_pilot_bootstrap as module

    closeout_dir = tmp_path / "closeout"
    closeout_dir.mkdir()
    closeout_report = closeout_dir / "001_production_landing_signoff_closeout.json"
    closeout_report.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T07:00:00+00:00",
                "status": "success",
                "final_status": "success",
                "missing_condition_count": 0,
                "secret_plaintext_output": False,
                "public_production_direct_launch": "No-Go",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "SIGNOFF_CLOSEOUT_DIR", closeout_dir)
    monkeypatch.setattr(
        module,
        "build_operations_console_landing_smoke",
        lambda: {"status": "success", "execute": True, "secret_plaintext_output": False},
    )
    monkeypatch.setattr(
        module,
        "build_production_landing_final_verification",
        lambda: {"status": "success", "passed_count": 9, "requirement_count": 9, "secret_plaintext_output": False},
    )
    monkeypatch.setattr(
        module,
        "build_production_pilot_evidence_bundle",
        lambda: {
            "status": "success",
            "controlled_pilot_ready": True,
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_pilot_bootstrap(
        output_dir=tmp_path / "out",
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    closeout = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_landing_signoff_closeout")
    final = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_landing_final_verification")
    bundle = next(item for item in payload["evidence_runs"] if item["evidence_id"] == "production_pilot_evidence_bundle")

    assert closeout["status"] == "success"
    assert closeout["final_status"] == "success"
    assert final["status"] == "success"
    assert bundle["status"] == "success"
    assert payload["signoff_closeout_passed"] is True
    assert payload["final_verification_passed"] is True
    assert payload["pilot_evidence_bundle_passed"] is True
    assert payload["operations_console_smoke_status"] == "success"


def test_latest_successful_real_llm_evidence_reads_existing_success_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "ok.json").write_text(
        json.dumps(
            {
                "status": "success",
                "real_llm_executed": True,
                "secret_plaintext_output": False,
                "generated_at": "2026-06-04T00:00:00+00:00",
                "domains": [
                    {
                        "domain_id": "real_llm",
                        "evidence": {"network_check_executed": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    evidence = _latest_successful_real_llm_evidence(report_dir)

    assert evidence["status"] == "success"
    assert evidence["real_llm_executed"] is True
    assert evidence["network_check_evidence_present"] is True


def test_latest_successful_real_llm_evidence_prefers_generated_at_over_mtime(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    current = report_dir / "100_current.json"
    stale = report_dir / "999_stale.json"
    base_payload = {
        "status": "success",
        "real_llm_executed": True,
        "secret_plaintext_output": False,
        "domains": [{"domain_id": "real_llm", "evidence": {"network_check_executed": True}}],
    }
    current.write_text(
        json.dumps({"generated_at": "2026-06-05T10:00:00+00:00", **base_payload}),
        encoding="utf-8",
    )
    stale.write_text(
        json.dumps({"generated_at": "2026-06-05T09:00:00+00:00", **base_payload}),
        encoding="utf-8",
    )
    os.utime(current, (1, 1))
    os.utime(stale, (2, 2))

    evidence = _latest_successful_real_llm_evidence(report_dir)

    assert evidence["latest_json_path"] == str(current)
    assert evidence["generated_at"] == "2026-06-05T10:00:00+00:00"
