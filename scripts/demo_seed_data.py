from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.harness.llm.pilot_report import (
    PilotReportCase,
    build_pilot_report,
    summarize_base_url,
    write_pilot_report_json,
    write_pilot_report_markdown,
)
from app.harness.metrics.metrics_store import SQLiteMetricsStore
from app.models.schemas import AuditEvent, RiskLevel, TaskRun, TaskStatus
from app.storage.approval_store import SQLiteApprovalStore
from app.storage.audit_store import SQLiteAuditStore
from app.storage.task_store import SQLiteTaskStore

DEFAULT_RUNTIME_DB = ROOT_DIR / "data" / "db" / "runtime.sqlite"
DEFAULT_METRICS_DB = ROOT_DIR / "data" / "db" / "runtime_metrics.sqlite"
DEFAULT_REPORT_DIR = ROOT_DIR / "docs" / "reports" / "real_llm_pilot"
DEFAULT_TRACE_FIXTURE = ROOT_DIR / "docs" / "demo_fixtures" / "trace_demo_events_v31.json"

TASK_PREFIX = "demo-v31-"
REPORT_ID = "demo-v31-pilot"


def _seed_ops_demo_db() -> None:
    init_script = ROOT_DIR / "scripts" / "init_demo_db.py"
    subprocess.run([sys.executable, str(init_script)], check=True, cwd=str(ROOT_DIR))


def _cleanup_runtime_rows(runtime_db_path: Path) -> None:
    with sqlite3.connect(runtime_db_path) as conn:
        conn.execute("DELETE FROM tasks WHERE task_id LIKE ?", (f"{TASK_PREFIX}%",))
        conn.execute("DELETE FROM approvals WHERE task_id LIKE ?", (f"{TASK_PREFIX}%",))
        conn.execute("DELETE FROM audit_events WHERE task_id LIKE ? OR event_type LIKE 'demo_v31_%'", (f"{TASK_PREFIX}%",))
        conn.commit()


def _cleanup_metrics_rows(metrics_db_path: Path) -> None:
    with sqlite3.connect(metrics_db_path) as conn:
        conn.execute("DELETE FROM runtime_task_metrics WHERE task_id LIKE ?", (f"{TASK_PREFIX}%",))
        conn.execute("DELETE FROM runtime_tool_metrics WHERE task_id LIKE ?", (f"{TASK_PREFIX}%",))
        conn.execute("DELETE FROM runtime_token_usage WHERE task_id LIKE ?", (f"{TASK_PREFIX}%",))
        conn.commit()


def _seed_runtime_data(runtime_db_path: Path) -> dict[str, Any]:
    task_store = SQLiteTaskStore(db_path=str(runtime_db_path))
    approval_store = SQLiteApprovalStore(db_path=str(runtime_db_path))
    audit_store = SQLiteAuditStore(db_path=str(runtime_db_path))

    _cleanup_runtime_rows(runtime_db_path)

    now = datetime.now()
    tasks = [
        TaskRun(
            task_id=f"{TASK_PREFIX}keyword-summary",
            query="演示任务：今日运营摘要",
            status=TaskStatus.completed,
            result={
                "mode": "keyword",
                "summary": "离线演示：今日 GMV 稳定，退款率可控。",
                "generator_used": "mock",
                "provider_used": "fake",
            },
            created_at=now,
            updated_at=now,
        ),
        TaskRun(
            task_id=f"{TASK_PREFIX}nl2sql-preview",
            query="演示任务：查询近 7 天订单量趋势",
            status=TaskStatus.completed,
            result={
                "mode": "nl2sql",
                "sql": "SELECT order_date, COUNT(*) AS order_count FROM orders GROUP BY order_date ORDER BY order_date DESC LIMIT 7;",
                "generator_used": "mock",
                "provider_used": "fake",
                "fallback_used": False,
            },
            created_at=now,
            updated_at=now,
        ),
        TaskRun(
            task_id=f"{TASK_PREFIX}approval-pending",
            query="演示任务：高风险工具审批示例",
            status=TaskStatus.waiting_approval,
            result={"requires_approval": True, "generator_used": "mock", "provider_used": "fake"},
            created_at=now,
            updated_at=now,
        ),
    ]

    task_store.save_task(tasks[0], mode="keyword")
    task_store.save_task(tasks[1], mode="nl2sql")
    task_store.save_task(tasks[2], mode="multitool")

    approval = approval_store.create_approval(
        task_id=tasks[2].task_id,
        tool_name="demo_sensitive_tool",
        action="export_customer_segment",
        risk_level=RiskLevel.high,
        impact_scope="demo_scope",
        agent_reason="演示审批流程：需要管理员确认后继续。",
        payload={
            "mode": "multitool",
            "risk_reason": "high_risk_demo_action",
            "approval_context": "demo_only",
        },
    )

    audit_events = [
        AuditEvent(
            event_type="demo_v31_seed_loaded",
            task_id=tasks[0].task_id,
            action="seed_demo_data",
            outcome="success",
            severity="info",
            detail={"dataset": "v3.1_demo_seed", "offline": True},
        ),
        AuditEvent(
            event_type="demo_v31_nl2sql_preview",
            task_id=tasks[1].task_id,
            action="nl2sql_preview",
            outcome="success",
            severity="info",
            detail={
                "request_id": "demo-v31-req-001",
                "provider": "fake",
                "model": "demo-mock-model",
                "fallback_used": False,
            },
        ),
        AuditEvent(
            event_type="demo_v31_approval_waiting",
            task_id=tasks[2].task_id,
            approval_id=approval.approval_id,
            action="approval_required",
            outcome="pending",
            severity="warn",
            detail={"risk_level": "high", "tool_name": "demo_sensitive_tool"},
        ),
    ]
    for event in audit_events:
        audit_store.append(event)

    return {
        "task_count": len(tasks),
        "approval_id": approval.approval_id,
        "audit_event_count": len(audit_events),
    }


def _seed_metrics_data(metrics_db_path: Path) -> dict[str, Any]:
    store = SQLiteMetricsStore(db_path=str(metrics_db_path))
    _cleanup_metrics_rows(metrics_db_path)

    ts = datetime.now(timezone.utc).isoformat()
    task_rows = [
        (f"{TASK_PREFIX}keyword-summary", "keyword", "completed", 120.5),
        (f"{TASK_PREFIX}nl2sql-preview", "nl2sql", "completed", 248.3),
        (f"{TASK_PREFIX}approval-pending", "multitool", "waiting_approval", 80.1),
    ]
    for task_id, mode, status, latency in task_rows:
        store.append_task_metric(task_id=task_id, mode=mode, status=status, latency_ms=latency, timestamp=ts)

    store.append_tool_metric(tool_name="demo_v31_read_tool", success=True, latency_ms=45.2, task_id=f"{TASK_PREFIX}keyword-summary", timestamp=ts)
    store.append_tool_metric(tool_name="demo_v31_guarded_tool", success=False, latency_ms=61.7, retry_count=1, task_id=f"{TASK_PREFIX}approval-pending", timestamp=ts)
    store.append_token_usage(task_id=f"{TASK_PREFIX}nl2sql-preview", prompt_tokens=120, completion_tokens=80, cost=0.0012, timestamp=ts)

    return {"task_metric_count": len(task_rows), "tool_metric_count": 2, "token_usage_count": 1}


def _seed_pilot_report(report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    for path in report_dir.glob(f"*{REPORT_ID}*.json"):
        path.unlink(missing_ok=True)
    for path in report_dir.glob(f"*{REPORT_ID}*.md"):
        path.unlink(missing_ok=True)

    case = PilotReportCase(
        scenario="nl2sql_demo",
        endpoint="/nl2sql/preview",
        request_id="demo-v31-req-001",
        provider="fake",
        model="demo-mock-model",
        base_url_summary=summarize_base_url(""),
        api_key_env="DEMO_API_KEY_ENV",
        api_key_present=False,
        real_call_attempted=False,
        real_call_succeeded=False,
        fallback_used=False,
        fallback_reason="",
        budget_action="allow",
        cache_hit=False,
        latency_ms=248.3,
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        cost=0.0012,
        error_type="",
        outcome="success",
        warnings=["demo_seed_offline"],
        evidence_links={"audit_event_type": "demo_v31_nl2sql_preview", "log_request_id": "demo-v31-req-001"},
        observability={"runtime_metric_keys": ["llm_budget", "llm_cache", "total_cost"]},
        evidence_notes=["demo_seed_v31"],
        detail={"notes": "演示数据已脱敏，不包含 prompt 原文与密钥原文。"},
    )

    report = build_pilot_report(
        cases=[case],
        commit="demo-seed-v31",
        environment="offline-demo",
        report_id=REPORT_ID,
    )
    json_path = write_pilot_report_json(report, output_dir=report_dir)
    md_path = write_pilot_report_markdown(report, output_dir=report_dir)
    return {"report_id": report.report_id, "json": str(json_path), "markdown": str(md_path)}


def _write_trace_fixture(trace_fixture_path: Path) -> dict[str, Any]:
    trace_fixture_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": f"{TASK_PREFIX}trace-demo",
        "events": [
            {
                "event_type": "task_started",
                "actor": "system",
                "detail": {"mode": "keyword"},
            },
            {
                "event_type": "plan_created",
                "actor": "planner",
                "detail": {"plan": "读取本地离线演示指标"},
            },
            {
                "event_type": "task_completed",
                "actor": "system",
                "detail": {"status": "completed", "offline": True},
            },
        ],
        "note": "该 trace fixture 仅用于演示，不包含 prompt 原文与敏感凭据。",
    }
    trace_fixture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"trace_fixture": str(trace_fixture_path)}


def seed_demo_data(
    *,
    runtime_db_path: Path,
    metrics_db_path: Path,
    pilot_report_dir: Path,
    trace_fixture_path: Path,
    skip_ops_db: bool = False,
) -> dict[str, Any]:
    if not skip_ops_db:
        _seed_ops_demo_db()

    runtime_summary = _seed_runtime_data(runtime_db_path)
    metrics_summary = _seed_metrics_data(metrics_db_path)
    report_summary = _seed_pilot_report(pilot_report_dir)
    trace_summary = _write_trace_fixture(trace_fixture_path)

    return {
        "status": "ok",
        "offline": True,
        "runtime_db_path": str(runtime_db_path),
        "metrics_db_path": str(metrics_db_path),
        "pilot_report_dir": str(pilot_report_dir),
        "skip_ops_db": bool(skip_ops_db),
        "runtime": runtime_summary,
        "metrics": metrics_summary,
        "pilot_report": report_summary,
        **trace_summary,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="初始化 v3.1 离线演示 seed 数据（默认 fake/offline）。")
    parser.add_argument("--runtime-db-path", default=str(DEFAULT_RUNTIME_DB))
    parser.add_argument("--metrics-db-path", default=str(DEFAULT_METRICS_DB))
    parser.add_argument("--pilot-report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--trace-fixture-path", default=str(DEFAULT_TRACE_FIXTURE))
    parser.add_argument("--skip-ops-db", action="store_true", help="跳过 ops_demo.sqlite 初始化")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = seed_demo_data(
        runtime_db_path=Path(args.runtime_db_path),
        metrics_db_path=Path(args.metrics_db_path),
        pilot_report_dir=Path(args.pilot_report_dir),
        trace_fixture_path=Path(args.trace_fixture_path),
        skip_ops_db=bool(args.skip_ops_db),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"status=ok report_json={summary['pilot_report']['json']}")
    print(f"status=ok report_markdown={summary['pilot_report']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
