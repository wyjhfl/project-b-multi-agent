from __future__ import annotations

import json
from pathlib import Path

from scripts.demo_artifact_bundle import build_demo_artifact_bundle


def test_demo_artifact_bundle_generates_required_outputs(tmp_path: Path):
    online_payload = {
        "status": "ok",
        "reason": "",
        "checks": {
            "health": {"status": "ok", "url": "http://127.0.0.1:65530/health", "body": {"status": "ok"}},
            "operations_summary": {
                "status": "ok",
                "url": "http://127.0.0.1:65530/operations/summary",
                "body": {"mode": "read_only", "runtime_metrics": {"total_prompt_tokens": 10, "total_cost": 0.1}},
            },
        },
    }
    seed_payload = {"status": "ok", "offline": True, "prompt": "should_redact"}

    summary = build_demo_artifact_bundle(
        artifact_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        seed_summary=seed_payload,
        online_smoke_result=online_payload,
    )

    run_dir = Path(summary["artifact_run_dir"])
    assert run_dir.exists()
    assert (run_dir / "demo_e2e_summary.json").exists()
    assert (run_dir / "online_smoke_result.json").exists()
    assert (run_dir / "seed_summary.json").exists()
    assert (run_dir / "pilot_report_index.json").exists()

    payload = json.loads((run_dir / "demo_e2e_summary.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "fake_offline_default"
    assert payload["real_llm_executed"] is False
    assert payload["acceptance_snapshot"]["json_path"]
    assert payload["acceptance_snapshot"]["markdown_path"]
    assert Path(payload["acceptance_snapshot"]["json_path"]).exists()
    assert Path(payload["acceptance_snapshot"]["markdown_path"]).exists()


def test_demo_artifact_bundle_handles_service_unavailable_with_skipped(tmp_path: Path):
    online_payload = {
        "status": "skipped",
        "reason": "service_unavailable",
        "checks": {
            "health": {
                "status": "skipped",
                "url": "http://127.0.0.1:65530/health",
                "error": "connection refused",
            }
        },
    }

    summary = build_demo_artifact_bundle(
        artifact_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        seed_summary=None,
        online_smoke_result=online_payload,
    )

    run_dir = Path(summary["artifact_run_dir"])
    payload = json.loads((run_dir / "demo_e2e_summary.json").read_text(encoding="utf-8"))
    assert payload["status"] == "completed_with_skipped_online_checks"
    assert payload["online_smoke"]["status"] == "skipped"
    assert payload["online_smoke"]["skipped_reason"] == "service_unavailable"
    assert payload["operations_summary"]["status"] == "skipped"


def test_demo_artifact_bundle_redacts_sensitive_fields(tmp_path: Path):
    online_payload = {
        "status": "ok",
        "checks": {
            "operations_summary": {
                "status": "ok",
                "url": "http://127.0.0.1:65530/operations/summary",
                "body": {
                    "prompt": "raw prompt text",
                    "raw_prompt": "raw prompt",
                    "query": "select * from user_private",
                    "api_key": "sk-should-not-leak",
                    "client_secret": "super-secret",
                    "password": "db-password",
                    "database_url": "postgresql://demo:secret@localhost:5432/db",
                    "redis_url": "redis://:password@localhost:6379/0",
                    "request_id": "req-demo-1",
                    "total_prompt_tokens": 321,
                },
            }
        },
    }

    summary = build_demo_artifact_bundle(
        artifact_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        seed_summary={"status": "ok", "sql_prompt": "select * from users", "token": "abc"},
        online_smoke_result=online_payload,
    )

    run_dir = Path(summary["artifact_run_dir"])
    merged = "\n".join(
        [
            (run_dir / "demo_e2e_summary.json").read_text(encoding="utf-8"),
            (run_dir / "online_smoke_result.json").read_text(encoding="utf-8"),
            (run_dir / "seed_summary.json").read_text(encoding="utf-8"),
            (run_dir / "operations_summary.json").read_text(encoding="utf-8"),
        ]
    )

    forbidden = [
        "raw prompt text",
        "select * from user_private",
        "sk-should-not-leak",
        "super-secret",
        "db-password",
        "postgresql://demo:secret@",
        "redis://:password@",
    ]
    for item in forbidden:
        assert item not in merged


def test_demo_artifact_bundle_records_acceptance_snapshot_paths(tmp_path: Path):
    summary = build_demo_artifact_bundle(
        artifact_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        seed_summary={"status": "ok"},
        online_smoke_result={"status": "ok", "checks": {}},
    )

    run_dir = Path(summary["artifact_run_dir"])
    payload = json.loads((run_dir / "demo_e2e_summary.json").read_text(encoding="utf-8"))
    snapshot_json = Path(payload["acceptance_snapshot"]["json_path"])
    snapshot_md = Path(payload["acceptance_snapshot"]["markdown_path"])

    assert snapshot_json.exists()
    assert snapshot_md.exists()
    assert payload["acceptance_snapshot"]["status"] in {
        "completed",
        "completed_with_skipped_online_checks",
        "completed_with_partial_online_checks",
    }
