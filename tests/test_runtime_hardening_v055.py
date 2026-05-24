from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.memory.short_term import ShortTermMemory
from app.harness.metrics.metrics_store import SQLiteMetricsStore
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, ToolSpec

client = TestClient(app)


def test_cost_summary_by_mode_attribution_stable():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "mode_attr.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed", timestamp="2025-01-01T10:00:00+00:00")
        store.append_task_metric("t1", "nl2sql", "completed", timestamp="2025-01-01T11:00:00+00:00")
        store.append_token_usage("t1", prompt_tokens=100, completion_tokens=50, cost=0.001, timestamp="2025-01-01T10:30:00+00:00")

        cs = store.cost_summary()
        assert cs["total_prompt_tokens"] == 100
        assert "keyword" in cs["by_mode"]
        assert cs["by_mode"]["keyword"]["prompt_tokens"] == 100


def test_cost_summary_time_filter_by_mode():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "time_mode.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed", timestamp="2025-01-01T10:00:00+00:00")
        store.append_task_metric("t2", "nl2sql", "completed", timestamp="2025-06-01T10:00:00+00:00")
        store.append_token_usage("t1", prompt_tokens=100, cost=0.001, timestamp="2025-01-01T10:30:00+00:00")
        store.append_token_usage("t2", prompt_tokens=200, cost=0.002, timestamp="2025-06-01T10:30:00+00:00")

        cs = store.cost_summary(start_time="2025-03-01T00:00:00+00:00")
        assert cs["total_prompt_tokens"] == 200
        assert "nl2sql" in cs["by_mode"]
        assert cs["by_mode"]["nl2sql"]["prompt_tokens"] == 200


def test_tool_metric_can_write_task_id():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "tool_tid.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_tool_metric("get_today_gmv", success=True, task_id="task_abc")

        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT task_id FROM runtime_tool_metrics")
            row = cursor.fetchone()
            assert row["task_id"] == "task_abc"


def test_toolgateway_call_no_task_id_compatible():
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(
            tool_name="test_tool",
            description="test",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            risk_level=RiskLevel.low,
            permission_scope="read",
            timeout_seconds=10.0,
            is_local=True,
        ),
        lambda: {"ok": True},
    )
    recorder = RuntimeMetricsRecorder()
    gateway.set_metrics_recorder(recorder)
    record = gateway.call("test_tool")
    assert record.success
    assert recorder.tool_call_count == 1


def test_toolgateway_call_with_task_id():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "gw_tid.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        recorder = RuntimeMetricsRecorder()
        recorder.set_metrics_store(store)

        gateway = ToolGateway()
        gateway.register(
            ToolSpec(
                tool_name="test_tool",
                description="test",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {}},
                risk_level=RiskLevel.low,
                permission_scope="read",
                timeout_seconds=10.0,
                is_local=True,
            ),
            lambda: {"ok": True},
        )
        gateway.set_metrics_recorder(recorder)

        record = gateway.call("test_tool", task_id="task_xyz")
        assert record.success

        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT task_id FROM runtime_tool_metrics")
            row = cursor.fetchone()
            assert row["task_id"] == "task_xyz"


def test_short_term_memory_summary():
    mem = ShortTermMemory()
    mem.add_message("s1", "user", "hello")
    mem.add_message("s1", "assistant", "hi")
    mem.add_message("s2", "user", "bye")

    s = mem.summary()
    assert s["session_count"] == 2
    assert s["message_count"] == 3
    assert len(s["sessions"]) == 2
    session_ids = [sess["session_id"] for sess in s["sessions"]]
    assert "s1" in session_ids
    assert "s2" in session_ids


def test_runtime_snapshot_no_private_access():
    resp = client.get("/runtime/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "memory_summary" in data
    assert "session_count" in data["memory_summary"]
    assert "message_count" in data["memory_summary"]


def test_runtime_snapshot_section_failure_not_500():
    reset_runtime_for_test()
    from app.main import get_memory

    original_get_memory = None
    try:
        import app.api.runtime_snapshot as snap_mod

        memory = get_memory()
        original_summary = memory.summary

        def broken_summary():
            raise RuntimeError("memory broken")

        memory.summary = broken_summary

        resp = client.get("/runtime/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data["memory_summary"]

        memory.summary = original_summary
    finally:
        reset_runtime_for_test()


def test_app_version_updated():
    assert app.version == "1.0.0"


def test_metrics_tools_summary_no_regression():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "tools_reg.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_tool_metric("get_today_gmv", success=True, latency_ms=50.0, task_id="t1")
        store.append_tool_metric("get_order_count", success=False, latency_ms=120.0, retry_count=1, task_id="t1")

        ts = store.tool_summary()
        assert ts["tool_call_count"] == 2
        assert ts["tool_failure_count"] == 1
        assert "by_tool" in ts
