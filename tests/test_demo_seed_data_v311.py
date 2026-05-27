from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.demo_seed_data import seed_demo_data


def test_demo_seed_data_generates_expected_artifacts(tmp_path: Path):
    runtime_db = tmp_path / "runtime.sqlite"
    metrics_db = tmp_path / "runtime_metrics.sqlite"
    report_dir = tmp_path / "pilot_reports"
    trace_fixture = tmp_path / "trace_fixture.json"

    summary = seed_demo_data(
        runtime_db_path=runtime_db,
        metrics_db_path=metrics_db,
        pilot_report_dir=report_dir,
        trace_fixture_path=trace_fixture,
        skip_ops_db=True,
    )

    assert summary["status"] == "ok"
    assert summary["offline"] is True
    assert summary["runtime"]["task_count"] == 3
    assert summary["metrics"]["task_metric_count"] == 3
    assert report_dir.exists()
    assert trace_fixture.exists()

    with sqlite3.connect(runtime_db) as conn:
        task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
        approval_count = conn.execute("SELECT COUNT(*) FROM approvals WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE task_id LIKE 'demo-v31-%' OR event_type LIKE 'demo_v31_%'"
        ).fetchone()[0]
    assert task_count >= 3
    assert approval_count >= 1
    assert audit_count >= 3

    with sqlite3.connect(metrics_db) as conn:
        metric_tasks = conn.execute("SELECT COUNT(*) FROM runtime_task_metrics WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
        metric_tools = conn.execute("SELECT COUNT(*) FROM runtime_tool_metrics WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
        metric_tokens = conn.execute("SELECT COUNT(*) FROM runtime_token_usage WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
    assert metric_tasks >= 3
    assert metric_tools >= 2
    assert metric_tokens >= 1

    report_json = Path(summary["pilot_report"]["json"])
    report_md = Path(summary["pilot_report"]["markdown"])
    assert report_json.exists()
    assert report_md.exists()
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    payload_text = json.dumps(payload, ensure_ascii=False)
    assert payload["report_id"] == "demo-v31-pilot"
    assert "REDACTED_PROMPT" not in payload_text
    assert "OPENAI_API_KEY" not in payload_text
    markdown_text = report_md.read_text(encoding="utf-8")
    assert "原始 prompt 文本" not in markdown_text
    assert "OPENAI_API_KEY" not in markdown_text


def test_demo_seed_data_idempotent_for_demo_prefix(tmp_path: Path):
    runtime_db = tmp_path / "runtime.sqlite"
    metrics_db = tmp_path / "runtime_metrics.sqlite"
    report_dir = tmp_path / "pilot_reports"
    trace_fixture = tmp_path / "trace_fixture.json"

    seed_demo_data(
        runtime_db_path=runtime_db,
        metrics_db_path=metrics_db,
        pilot_report_dir=report_dir,
        trace_fixture_path=trace_fixture,
        skip_ops_db=True,
    )
    seed_demo_data(
        runtime_db_path=runtime_db,
        metrics_db_path=metrics_db,
        pilot_report_dir=report_dir,
        trace_fixture_path=trace_fixture,
        skip_ops_db=True,
    )

    with sqlite3.connect(runtime_db) as conn:
        task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
        approval_count = conn.execute("SELECT COUNT(*) FROM approvals WHERE task_id LIKE 'demo-v31-%'").fetchone()[0]
    assert task_count == 3
    assert approval_count == 1
