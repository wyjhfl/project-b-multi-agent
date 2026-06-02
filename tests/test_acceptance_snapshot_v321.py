from __future__ import annotations

import json
from pathlib import Path

from scripts.acceptance_snapshot import REDACTED_PROMPT_PLACEHOLDER, build_acceptance_snapshot


def test_acceptance_snapshot_generates_json_and_markdown(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path, base_url="http://127.0.0.1:65530")
    json_path = Path(summary["json_path"])
    md_path = Path(summary["markdown_path"])

    assert json_path.exists()
    assert md_path.exists()
    assert summary["status"] in {"completed_with_skipped_online_checks", "completed_with_partial_online_checks", "completed"}

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["snapshot_id"]
    assert payload["generated_at"]
    assert payload["commit"]
    assert payload["version"] == "3.5.0"
    assert "health_summary" in payload
    assert "deployment_summary" in payload
    assert "operations_summary" in payload
    assert "runtime_metrics_summary" in payload
    assert "audit_recent_events" in payload
    assert "pilot_reports_index" in payload
    assert "demo_evidence_paths" in payload
    assert "boundary_declarations" in payload


def test_acceptance_snapshot_preserves_evidence_metrics(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path, base_url="http://127.0.0.1:65530")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    runtime_metrics = payload["runtime_metrics_summary"]
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "total_prompt_tokens",
        "total_completion_tokens",
        "token_usage_count",
        "total_cost",
    ):
        value = runtime_metrics.get(key, 0)
        assert value != REDACTED_PROMPT_PLACEHOLDER
        assert isinstance(value, (int, float))

    op_runtime_metrics = payload["operations_summary"]["runtime_metrics"]
    for key in ("total_prompt_tokens", "total_completion_tokens", "total_cost"):
        value = op_runtime_metrics.get(key, 0)
        assert value != REDACTED_PROMPT_PLACEHOLDER
        assert isinstance(value, (int, float))


def test_acceptance_snapshot_redacts_sensitive_content(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path, base_url="http://127.0.0.1:65530")
    json_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    md_text = Path(summary["markdown_path"]).read_text(encoding="utf-8")
    merged = json_text + "\n" + md_text

    forbidden = [
        "raw_prompt",
        "sql_prompt",
        "sk-",
        "client_secret",
        "password",
        "JWT_SECRET=",
        "DATABASE_URL=",
        "REDIS_URL=",
        "postgresql://user:secret@",
        "redis://:password@",
    ]
    for raw in forbidden:
        assert raw not in merged


def test_acceptance_snapshot_marks_online_skipped_when_service_unavailable(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path, base_url="http://127.0.0.1:65530")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert payload["online_checks"]["status"] in {"skipped", "partial", "ok"}
    if payload["online_checks"]["status"] == "skipped":
        assert payload["status"] == "completed_with_skipped_online_checks"
        assert payload["skipped"]


def test_acceptance_snapshot_output_dir_override(tmp_path: Path):
    out_dir = tmp_path / "custom_snapshots"
    summary = build_acceptance_snapshot(output_dir=out_dir, base_url="http://127.0.0.1:65530")
    assert Path(summary["json_path"]).parent == out_dir
    assert Path(summary["markdown_path"]).parent == out_dir
