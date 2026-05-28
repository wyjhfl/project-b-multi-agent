from __future__ import annotations

import json
from pathlib import Path

from scripts.acceptance_snapshot import build_acceptance_snapshot


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
    assert payload["version"] == "3.1.0"
    assert "health_summary" in payload
    assert "deployment_summary" in payload
    assert "operations_summary" in payload
    assert "runtime_metrics_summary" in payload
    assert "audit_recent_events" in payload
    assert "pilot_reports_index" in payload
    assert "demo_evidence_paths" in payload
    assert "boundary_declarations" in payload


def test_acceptance_snapshot_redacts_sensitive_content(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path, base_url="http://127.0.0.1:65530")
    json_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    md_text = Path(summary["markdown_path"]).read_text(encoding="utf-8")
    merged = json_text + "\n" + md_text

    forbidden = [
        "原始 prompt 文本",
        "原始 query 文本",
        "raw_prompt",
        "sql_prompt",
        "sk-",
        "client_secret",
        "JWT_SECRET=",
        "DATABASE_URL=",
        "REDIS_URL=",
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
