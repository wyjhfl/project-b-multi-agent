from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import AuditEvent, RiskLevel, ToolSpec
from app.storage.audit_store import SQLiteAuditStore

client = TestClient(app)


def test_audit_store_filename_only_db_path():
    db_file = "runtime_test.sqlite"
    db_path = os.path.join(os.path.dirname(__file__), db_file)
    try:
        store = SQLiteAuditStore(db_path=db_path)
        event = AuditEvent(
            event_type="path_test",
            actor="tester",
            action="test_filename_path",
            outcome="success",
        )
        store.append(event)
        got = store.get_event(event.event_id)
        assert got is not None
        assert got["event_type"] == "path_test"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_audit_event_timestamp_has_tzinfo():
    event = AuditEvent(event_type="tz_test", action="check_tz")
    assert event.timestamp.tzinfo is not None


def test_audit_event_timestamp_is_utc():
    event = AuditEvent(event_type="utc_test", action="check_utc")
    utc_offset = event.timestamp.utcoffset()
    assert utc_offset is not None
    assert utc_offset.total_seconds() == 0


def test_audit_store_get_event_timestamp_contains_offset():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_tz.sqlite")
        store = SQLiteAuditStore(db_path=db_path)
        event = AuditEvent(event_type="tz_store_test", action="store_tz")
        store.append(event)

        got = store.get_event(event.event_id)
        assert got is not None
        ts = got["timestamp"]
        assert "+00:00" in ts or "Z" in ts


def test_audit_store_query_by_start_time():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_time_query.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        old_event = AuditEvent(
            event_type="old_event",
            action="old",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        store.append(old_event)

        new_event = AuditEvent(
            event_type="new_event",
            action="new",
            timestamp=datetime.now(timezone.utc),
        )
        store.append(new_event)

        recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        results = store.query_events(start_time=recent)
        assert len(results) >= 1
        assert all(r["event_type"] == "new_event" for r in results)


def test_audit_store_query_by_end_time():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_end_time.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        store.append(AuditEvent(event_type="early_event", action="early"))
        store.append(AuditEvent(event_type="late_event", action="late"))

        cutoff = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        results = store.query_events(end_time=cutoff)
        assert len(results) >= 2


def test_audit_store_query_time_range():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_range.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        store.append(AuditEvent(event_type="range_event", action="in_range"))

        start = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        results = store.query_events(start_time=start, end_time=end)
        assert len(results) >= 1
        assert results[0]["event_type"] == "range_event"


def test_audit_store_query_combined_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_combined.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        store.append(AuditEvent(event_type="combined_test", action="combo", outcome="success"))
        store.append(AuditEvent(event_type="combined_test", action="combo2", outcome="failed"))
        store.append(AuditEvent(event_type="other_event", action="other", outcome="success"))

        start = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        results = store.query_events(event_type="combined_test", outcome="success", start_time=start)
        assert len(results) == 1
        assert results[0]["outcome"] == "success"


def test_audit_store_query_invalid_time_ignored():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_invalid_time.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        store.append(AuditEvent(event_type="invalid_time_test", action="test"))

        results = store.query_events(start_time="not-a-valid-time")
        assert len(results) >= 1


def test_audit_store_limit_bounds_with_time():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_limit_time.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        for i in range(10):
            store.append(AuditEvent(event_type="limit_test", action=f"action_{i}"))

        results = store.query_events(limit=0)
        assert len(results) == 10

        results = store.query_events(limit=5)
        assert len(results) == 5

        results = store.query_events(limit=600)
        assert len(results) == 10


def test_runtime_metrics_recorder_task():
    recorder = RuntimeMetricsRecorder()
    recorder.record_task("t1", "keyword", "completed", latency_ms=100.0)
    recorder.record_task("t2", "nl2sql", "failed", latency_ms=200.0)
    recorder.record_task("t3", "multitool", "success", latency_ms=150.0)

    s = recorder.summary()
    assert s["task_count"] == 3
    assert s["success_count"] == 2
    assert s["failed_count"] == 1
    assert s["avg_task_latency_ms"] == pytest.approx(150.0)


def test_runtime_metrics_recorder_status_breakdown():
    recorder = RuntimeMetricsRecorder()
    recorder.record_task("t1", "keyword", "completed")
    recorder.record_task("t2", "multitool", "waiting_approval")
    recorder.record_task("t3", "keyword", "cancelled")
    recorder.record_task("t4", "nl2sql", "failed")
    recorder.record_task("t5", "keyword", "unknown_status")

    s = recorder.summary()
    assert s["success_count"] == 1
    assert s["waiting_approval_count"] == 1
    assert s["cancelled_count"] == 1
    assert s["failed_count"] == 1
    assert s["unknown_status_count"] == 1
    assert s["task_count"] == 5


def test_runtime_metrics_recorder_tool_call():
    recorder = RuntimeMetricsRecorder()
    recorder.record_tool_call("get_today_gmv", success=True, latency_ms=10.0)
    recorder.record_tool_call("dangerous_tool", success=False, latency_ms=5.0)

    s = recorder.summary()
    assert s["tool_call_count"] == 2
    assert s["tool_failure_count"] == 1


def test_runtime_metrics_recorder_token_usage():
    recorder = RuntimeMetricsRecorder()
    recorder.record_token_usage("t1", prompt_tokens=100, completion_tokens=50, cost=0.01)
    recorder.record_token_usage("t2", prompt_tokens=200, completion_tokens=100, cost=0.02)

    s = recorder.summary()
    assert s["total_prompt_tokens"] == 300
    assert s["total_completion_tokens"] == 150
    assert s["total_cost"] == pytest.approx(0.03)


def test_runtime_metrics_recorder_empty_summary():
    recorder = RuntimeMetricsRecorder()
    s = recorder.summary()
    assert s["task_count"] == 0
    assert s["success_count"] == 0
    assert s["failed_count"] == 0
    assert s["waiting_approval_count"] == 0
    assert s["cancelled_count"] == 0
    assert s["unknown_status_count"] == 0
    assert s["tool_call_count"] == 0
    assert s["tool_failure_count"] == 0
    assert s["total_prompt_tokens"] == 0
    assert s["total_completion_tokens"] == 0
    assert s["total_cost"] == 0.0
    assert s["avg_task_latency_ms"] == 0.0


def test_metrics_api_runtime():
    reset_runtime_for_test()
    resp = client.get("/metrics/runtime")
    assert resp.status_code == 200
    data = resp.json()
    assert "task_count" in data
    assert "success_count" in data
    assert "failed_count" in data
    assert "waiting_approval_count" in data
    assert "cancelled_count" in data
    assert "unknown_status_count" in data
    assert "tool_call_count" in data
    assert "tool_failure_count" in data
    assert "total_prompt_tokens" in data
    assert "total_completion_tokens" in data
    assert "total_cost" in data
    assert "avg_task_latency_ms" in data
    reset_runtime_for_test()


def test_tool_gateway_metrics_on_success():
    gateway = ToolGateway()
    recorder = RuntimeMetricsRecorder()
    gateway.set_metrics_recorder(recorder)

    gateway.register(
        ToolSpec(tool_name="metrics_test_tool", description="test", risk_level=RiskLevel.low, source="local", is_local=True),
        lambda: {"result": "ok"},
    )

    record = gateway.call("metrics_test_tool")
    assert record.success is True
    assert recorder.tool_call_count == 1
    assert recorder.tool_failure_count == 0


def test_tool_gateway_metrics_on_failure():
    gateway = ToolGateway()
    recorder = RuntimeMetricsRecorder()
    gateway.set_metrics_recorder(recorder)

    record = gateway.call("nonexistent_tool")
    assert record.success is False
    assert recorder.tool_call_count == 1
    assert recorder.tool_failure_count == 1


def test_tool_gateway_metrics_no_recorder():
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(tool_name="no_metrics_tool", description="test", risk_level=RiskLevel.low, source="local", is_local=True),
        lambda: {"result": "ok"},
    )
    record = gateway.call("no_metrics_tool")
    assert record.success is True


def test_metrics_does_not_affect_trace():
    gateway = ToolGateway()
    recorder = RuntimeMetricsRecorder()
    trace = TraceRecorder()
    gateway.set_metrics_recorder(recorder)

    gateway.register(
        ToolSpec(tool_name="trace_test_tool", description="test", risk_level=RiskLevel.low, source="local", is_local=True),
        lambda: {"result": "ok"},
    )

    record = gateway.call("trace_test_tool")
    assert record.success is True
    assert recorder.tool_call_count == 1

    trace.record("tool_called", task_id="t1", detail={"tool_name": "trace_test_tool"})
    entries = trace.get_events(task_id="t1")
    assert len(entries) >= 1


def test_metrics_does_not_affect_audit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_metrics_audit.sqlite")
        store = SQLiteAuditStore(db_path=db_path)

        gateway = ToolGateway()
        recorder = RuntimeMetricsRecorder()
        gateway.set_metrics_recorder(recorder)

        gateway.register(
            ToolSpec(tool_name="audit_metrics_tool", description="test", risk_level=RiskLevel.low, source="local", is_local=True),
            lambda: {"result": "ok"},
        )

        gateway.call("audit_metrics_tool")
        assert recorder.tool_call_count == 1

        event = AuditEvent(event_type="tool_called", action="audit_metrics_tool", outcome="success")
        store.append(event)
        events = store.query_events(event_type="tool_called")
        assert len(events) == 1


def test_audit_api_time_range_query():
    reset_runtime_for_test()

    resp = client.post("/tasks", json={"query": "今日GMV"})
    assert resp.status_code == 200

    start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    resp = client.get("/audit/events", params={"start_time": start, "end_time": end})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    reset_runtime_for_test()
