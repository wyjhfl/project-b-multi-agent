from __future__ import annotations

import json
from pathlib import Path

from scripts.capacity_load_test_readiness_plan import build_capacity_load_test_readiness_plan


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_capacity_env(monkeypatch) -> None:
    for key in [
        "SRE_CAPACITY_TEST_ENABLED",
        "SRE_LOAD_TEST_DRY_RUN_ENABLED",
        "SRE_SOAK_TEST_ENABLED",
        "SRE_TARGET_CONCURRENCY",
        "SRE_TARGET_RPS",
        "SRE_TARGET_P95_LATENCY_MS",
        "SRE_TARGET_ERROR_RATE_PERCENT",
        "SRE_TEST_DURATION_MINUTES",
        "SRE_CAPACITY_TEST_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_capacity_load_test_readiness_plan_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_capacity_env(monkeypatch)
    summary = build_capacity_load_test_readiness_plan(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["load_test_executed"] is False
    assert summary["soak_test_executed"] is False
    assert summary["database_connected"] is False
    assert summary["redis_connected"] is False
    assert payload["version"] == "3.8.0"
    assert payload["phase"] == "v3.8 Phase 18.4"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_capacity_load_test_readiness_plan_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_capacity_env(monkeypatch)
    payload = _read_payload(build_capacity_load_test_readiness_plan(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "critical_endpoint_inventory",
        "traffic_model_targets",
        "request_guard_and_abuse_controls",
        "observability_for_capacity_test",
        "load_test_dry_run_evidence",
        "soak_test_readiness",
        "runbook_linkage",
        "regression_test_coverage",
    } <= check_ids


def test_capacity_load_test_readiness_plan_keeps_skipped_without_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_CAPACITY_TEST_ENABLED", "true")
    monkeypatch.setenv("SRE_LOAD_TEST_DRY_RUN_ENABLED", "true")
    monkeypatch.setenv("SRE_SOAK_TEST_ENABLED", "true")
    monkeypatch.setenv("SRE_TARGET_CONCURRENCY", "50")
    monkeypatch.setenv("SRE_TARGET_RPS", "100")
    monkeypatch.setenv("SRE_TARGET_P95_LATENCY_MS", "500")
    monkeypatch.setenv("SRE_TARGET_ERROR_RATE_PERCENT", "1")

    payload = _read_payload(build_capacity_load_test_readiness_plan(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["load_test_executed"] is False
    assert payload["soak_test_executed"] is False
    assert "evidence:load_test_plan_or_report_missing" in payload["missing_conditions"]
    assert "evidence:soak_test_report_missing" in payload["missing_conditions"]


def test_capacity_load_test_readiness_plan_does_not_leak_target_or_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_CAPACITY_TEST_BASE_URL", "https://user:password@example.com/load")
    monkeypatch.setenv("SRE_TARGET_RPS", "sk-capacity-sensitive")

    summary = build_capacity_load_test_readiness_plan(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "password@example" not in merged
    assert "sk-capacity-sensitive" not in merged
    assert "SRE_CAPACITY_TEST_BASE_URL" in merged
    assert "SRE_TARGET_RPS" in merged


def test_capacity_load_test_readiness_plan_records_local_evidence_without_execution(tmp_path: Path, monkeypatch) -> None:
    _clear_capacity_env(monkeypatch)
    payload = _read_payload(build_capacity_load_test_readiness_plan(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["metrics_api"]["present"] is True
    assert payload["local_checks"]["rate_limit"]["present"] is True
    assert payload["local_checks"]["abuse_guard"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["load_test_executed"] is False
