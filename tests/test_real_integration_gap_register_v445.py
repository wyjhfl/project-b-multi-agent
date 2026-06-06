from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.real_integration_gap_register import build_real_integration_gap_register


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _make_evidence_dirs(root: Path) -> dict[str, Path]:
    mapping = {
        "real_integration_env_profile": root / "real_integration_env_profile",
        "real_integration_smoke_plan": root / "real_integration_smoke_plan",
        "real_integration_staging_smoke": root / "real_integration_staging_smoke",
        "real_integration_readiness": root / "real_integration_readiness",
        "real_llm_provider_acceptance_gate": root / "real_llm_provider_acceptance_gate",
        "external_mcp_acceptance_gate": root / "external_mcp_acceptance_gate",
        "store_redis_readiness_drill": root / "store_redis_readiness_drill",
        "real_integration_staging_gate": root / "real_integration_staging_gate",
        "production_migration_drill": root / "production_migration_drill",
    }
    for directory in mapping.values():
        directory.mkdir(parents=True, exist_ok=True)
    return mapping


def _write_json(directory: Path, name: str, payload: dict) -> None:
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_payload(*, status: str = "partial", missing_conditions: list[str] | None = None) -> dict:
    return {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "phase": "demo-phase",
        "version": "demo-version",
        "status": status,
        "read_only": True,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "missing_conditions": missing_conditions or [],
    }


def test_real_integration_gap_register_generates_json_and_markdown(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["phase"] == "v4.4 Phase 24.6 Real Integration Gap Register"
    assert payload["version"] == "4.4.5"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert summary["evidence_count"] == 9
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_gap_register_groups_domain_actions(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(
        evidence_dirs["real_integration_env_profile"],
        "001.json",
        _base_payload(
            status="skipped",
            missing_conditions=[
                "opt_in:REAL_LLM_SMOKE_ENABLED",
                "opt_in:STORAGE_BACKEND_postgres",
                "opt_in:REDIS_ENABLED",
                "opt_in:MCP_MODE_real",
            ],
        ),
    )
    for key, directory in evidence_dirs.items():
        if key != "real_integration_env_profile":
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    domains = {item["domain"] for item in payload["gap_items"]}

    assert payload["status"] == "skipped"
    assert {"real_llm", "postgres", "redis", "external_mcp"}.issubset(domains)
    assert payload["go_no_go"]["combined_staging_gate"] == "Needs-Input"
    assert all(item["status"] == "open" for item in payload["gap_items"])


def test_real_integration_gap_register_manual_review_when_no_gaps(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for directory in evidence_dirs.values():
        _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["gap_count"] == 0
    assert payload["go_no_go"]["combined_staging_gate"] == "Manual-Review"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_real_integration_gap_register_blocks_secret_like_evidence_without_leaking_plaintext(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    secret_payload = _base_payload(status="partial")
    secret_payload["note"] = "token=sk-sensitive-value"
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", secret_payload)
    for key, directory in evidence_dirs.items():
        if key != "real_integration_env_profile":
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "sk-sensitive-value" not in merged
    assert "token=sk-sensitive-value" not in merged


def test_real_integration_gap_register_allows_secret_managed_placeholders(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_payload(status="partial")
        if key == "real_integration_staging_smoke":
            payload["required_env"] = [
                "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                "DATABASE_URL=<secret-managed-url>",
            ]
        _write_json(directory, "001.json", payload)

    summary = build_real_integration_gap_register(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert payload["status"] == "partial"
    assert smoke["status"] == "partial"
    assert smoke["blocking_reasons"] == []


def test_real_integration_gap_register_blocks_unexpected_execution_flag(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    abnormal = _base_payload(status="partial")
    abnormal["database_connected"] = True
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", abnormal)
    for key, directory in evidence_dirs.items():
        if key != "store_redis_readiness_drill":
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    store_item = next(
        item for item in payload["evidence_index"] if item["evidence_id"] == "store_redis_readiness_drill"
    )

    assert payload["status"] == "blocked"
    assert "unexpected_true_flag:database_connected" in store_item["blocking_reasons"]


def test_real_integration_gap_register_offsets_stale_missing_conditions_with_controlled_success(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(
        evidence_dirs["real_integration_env_profile"],
        "999_latest_skipped.json",
        _base_payload(
            status="skipped",
            missing_conditions=[
                "env:REAL_LLM_MODEL",
                "opt_in:STORAGE_BACKEND_postgres",
                "opt_in:REDIS_ENABLED",
                "opt_in:MCP_MODE_real",
            ],
        ),
    )
    success_smoke = _base_payload(status="success")
    success_smoke["real_llm_executed"] = True
    success_smoke["database_connected"] = True
    success_smoke["redis_connected"] = True
    success_smoke["external_mcp_connected"] = True
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001_success.json", success_smoke)
    _write_json(evidence_dirs["real_integration_staging_smoke"], "999_latest_skipped.json", _base_payload(status="skipped"))

    migration = _base_payload(status="success")
    migration["database_connected"] = True
    migration["migration_executed"] = True
    _write_json(evidence_dirs["production_migration_drill"], "001_success.json", migration)
    _write_json(evidence_dirs["production_migration_drill"], "999_latest_skipped.json", _base_payload(status="skipped"))

    for key, directory in evidence_dirs.items():
        if not any(directory.glob("*.json")):
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=evidence_dirs["real_integration_staging_smoke"],
    )
    payload = _read_payload(summary)
    domains = {item["domain"] for item in payload["gap_items"]}
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert payload["status"] == "partial"
    assert domains.isdisjoint({"real_llm", "postgres", "redis", "external_mcp"})
    assert smoke["latest_json_path"].endswith("001_success.json")
    assert smoke["blocking_reasons"] == []


def test_real_integration_gap_register_does_not_prefer_historical_blocked_without_current_risk(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_integration_staging_gate":
            _write_json(directory, "001_old_blocked.json", _base_payload(status="blocked", missing_conditions=["old:block"]))
            _write_json(directory, "999_latest_skipped.json", _base_payload(status="skipped", missing_conditions=["upstream_status:skipped"]))
        else:
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    gate = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_gate")

    assert payload["status"] == "skipped"
    assert gate["status"] == "skipped"
    assert gate["latest_json_path"].endswith("999_latest_skipped.json")


def test_real_integration_gap_register_does_not_prefer_historical_secret_failed_over_newer_safe_report(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_integration_staging_smoke":
            old_failed = directory / "001_old_failed.json"
            newer_safe = directory / "999_newer_skipped.json"
            old_failed.write_text(
                json.dumps(
                    {
                        **_base_payload(status="failed"),
                        "generated_at": "2026-06-05T09:00:00+00:00",
                        "note": "token=sk-old-failed-secret",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            newer_safe.write_text(
                json.dumps(
                    {
                        **_base_payload(status="skipped"),
                        "generated_at": "2026-06-05T10:00:00+00:00",
                        "missing_conditions": ["cli:--execute_not_requested"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.utime(old_failed, (2, 2))
            os.utime(newer_safe, (1, 1))
        else:
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert smoke["latest_json_path"] == str(evidence_dirs["real_integration_staging_smoke"] / "999_newer_skipped.json")
    assert smoke["status"] == "skipped"
    assert smoke["blocking_reasons"] == []
    assert payload["status"] == "skipped"


def test_real_integration_gap_register_prefers_generated_at_with_same_rank(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_integration_staging_gate":
            current = directory / "100_current.json"
            stale = directory / "999_stale.json"
            current.write_text(
                json.dumps(
                    {
                        **_base_payload(status="partial"),
                        "generated_at": "2026-06-05T10:00:00+00:00",
                        "missing_conditions": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stale.write_text(
                json.dumps(
                    {
                        **_base_payload(status="partial"),
                        "generated_at": "2026-06-05T09:00:00+00:00",
                        "missing_conditions": ["stale:condition"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.utime(current, (1, 1))
            os.utime(stale, (2, 2))
        else:
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)
    gate = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_gate")

    assert gate["latest_json_path"] == str(evidence_dirs["real_integration_staging_gate"] / "100_current.json")
    assert gate["missing_conditions"] == []


def test_real_integration_gap_register_ignores_upstream_skipped_warning_on_partial_gate(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_integration_staging_gate":
            _write_json(
                directory,
                "001.json",
                _base_payload(status="partial", missing_conditions=["upstream_status:skipped"]),
            )
        else:
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["gap_count"] == 0


def test_real_integration_gap_register_offsets_staging_smoke_opt_in_when_smoke_verified(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(
        evidence_dirs["real_integration_env_profile"],
        "001.json",
        _base_payload(status="skipped", missing_conditions=["opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED"]),
    )
    smoke = _base_payload(status="success")
    smoke["database_connected"] = True
    smoke["redis_connected"] = True
    smoke["external_mcp_connected"] = True
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001.json", smoke)
    for key, directory in evidence_dirs.items():
        if not any(directory.glob("*.json")):
            _write_json(directory, "001.json", _base_payload(status="partial"))

    summary = build_real_integration_gap_register(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=tmp_path / "empty_llm_reports",
    )
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["gap_count"] == 0
