from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.harness.memory.short_term import ShortTermMemory
from app.harness.metrics.metrics_store import SQLiteMetricsStore
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.harness.reflection.self_check import SelfCheckEngine
from app.harness.skills.registry import SkillRegistry
from app.main import app, reset_runtime_for_test
from app.models.schemas import TaskRun

client = TestClient(app)


def test_sqlite_metrics_store_init():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_metrics.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        assert os.path.exists(db_path)


def test_sqlite_metrics_store_append_task_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_metrics.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed", latency_ms=100.0)
        store.append_task_metric("t2", "nl2sql", "failed", latency_ms=200.0)
        store.append_task_metric("t3", "keyword", "waiting_approval")

        s = store.summary()
        assert s["task_count"] == 3
        assert s["success_count"] == 1
        assert s["failed_count"] == 1
        assert s["waiting_approval_count"] == 1
        assert s["avg_task_latency_ms"] == pytest.approx(150.0)


def test_sqlite_metrics_store_append_tool_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_metrics.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_tool_metric("get_today_gmv", success=True, latency_ms=50.0, retry_count=0)
        store.append_tool_metric("get_order_count", success=False, latency_ms=120.0, retry_count=2)

        s = store.summary()
        assert s["tool_call_count"] == 2
        assert s["tool_failure_count"] == 1

        ts = store.tool_summary()
        assert ts["tool_call_count"] == 2
        assert ts["tool_failure_count"] == 1
        assert ts["retry_count"] == 2
        assert "get_today_gmv" in ts["by_tool"]
        assert "get_order_count" in ts["by_tool"]
        assert ts["by_tool"]["get_order_count"]["failure_count"] == 1


def test_sqlite_metrics_store_append_token_and_cost_summary():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_metrics.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed")
        store.append_token_usage("t1", prompt_tokens=100, completion_tokens=50, cost=0.002)
        store.append_token_usage("t1", prompt_tokens=200, completion_tokens=100, cost=0.004)

        cs = store.cost_summary()
        assert cs["total_prompt_tokens"] == 300
        assert cs["total_completion_tokens"] == 150
        assert cs["total_cost"] == pytest.approx(0.006)
        assert "keyword" in cs["by_mode"]


def test_sqlite_metrics_store_limit_boundary():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_metrics.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        for i in range(10):
            store.append_task_metric(f"t{i}", "keyword", "completed")

        s0 = store.summary(limit=0)
        assert s0["task_count"] == 10

        s_neg = store.summary(limit=-5)
        assert s_neg["task_count"] == 10

        s_big = store.summary(limit=1000)
        assert s_big["task_count"] == 10


def test_sqlite_metrics_store_db_path_no_dirname():
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            db_path = "test_no_dir.sqlite"
            store = SQLiteMetricsStore(db_path=db_path)
            store.append_task_metric("t1", "keyword", "completed")
            assert os.path.exists(os.path.join(tmp, db_path))
        finally:
            os.chdir(old_cwd)


def test_runtime_metrics_recorder_dual_write():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "dual_write.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        recorder = RuntimeMetricsRecorder()
        recorder.set_metrics_store(store)

        recorder.record_task("t1", "keyword", "completed", latency_ms=100.0)
        recorder.record_tool_call("get_today_gmv", success=True, latency_ms=50.0)
        recorder.record_token_usage("t1", prompt_tokens=100, completion_tokens=50, cost=0.001)

        mem_summary = recorder.summary()
        assert mem_summary["task_count"] == 1
        assert mem_summary["tool_call_count"] == 1
        assert mem_summary["total_prompt_tokens"] == 100

        db_summary = store.summary()
        assert db_summary["task_count"] == 1
        assert db_summary["tool_call_count"] == 1
        assert db_summary["total_prompt_tokens"] == 100


def test_runtime_metrics_recorder_sqlite_failure_no_crash():
    recorder = RuntimeMetricsRecorder()

    class BrokenStore:
        def append_task_metric(self, **kwargs):
            raise RuntimeError("db broken")
        def append_tool_metric(self, **kwargs):
            raise RuntimeError("db broken")
        def append_token_usage(self, **kwargs):
            raise RuntimeError("db broken")

    recorder.set_metrics_store(BrokenStore())

    recorder.record_task("t1", "keyword", "completed")
    recorder.record_tool_call("get_today_gmv", success=True)
    recorder.record_token_usage("t1", prompt_tokens=100)

    assert recorder.task_count == 1
    assert recorder.tool_call_count == 1
    assert recorder.total_prompt_tokens == 100


def test_metrics_runtime_api_compatible():
    resp = client.get("/metrics/runtime")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = [
        "task_count", "success_count", "failed_count",
        "waiting_approval_count", "cancelled_count", "unknown_status_count",
        "tool_call_count", "tool_failure_count",
        "total_prompt_tokens", "total_completion_tokens", "total_cost",
        "avg_task_latency_ms", "reflection_count", "reflection_failed_count",
        "skill_match_count",
    ]
    for f in required_fields:
        assert f in data, f"missing field: {f}"


def test_metrics_cost_summary_api():
    resp = client.get("/metrics/cost/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_prompt_tokens" in data
    assert "total_completion_tokens" in data
    assert "total_cost" in data
    assert "by_mode" in data
    assert "by_day" in data


def test_metrics_tools_summary_api():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "tools_api.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_tool_metric("get_today_gmv", success=True, latency_ms=50.0)
        store.append_tool_metric("get_order_count", success=False, latency_ms=120.0, retry_count=1)

        ts = store.tool_summary()
        assert "by_tool" in ts
        assert "get_today_gmv" in ts["by_tool"]
        assert "get_order_count" in ts["by_tool"]
        assert ts["by_tool"]["get_order_count"]["failure_count"] == 1


def test_metrics_tasks_summary_api():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "tasks_api.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed")
        store.append_task_metric("t2", "nl2sql", "failed")
        store.append_task_metric("t3", "multitool", "waiting_approval")
        store.append_task_metric("t4", "keyword", "cancelled")
        store.append_task_metric("t5", "auto", "unknown_status")

        ts = store.task_summary()
        assert ts["task_count"] == 5
        assert ts["success_count"] == 1
        assert ts["failed_count"] == 1
        assert ts["waiting_approval_count"] == 1
        assert ts["cancelled_count"] == 1
        assert ts["unknown_status_count"] == 1
        assert "by_mode" in ts
        assert "keyword" in ts["by_mode"]
        assert ts["by_mode"]["keyword"]["count"] == 2


def test_runtime_snapshot_api():
    resp = client.get("/runtime/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "app_version" in data
    assert "metrics_summary" in data
    assert "cost_summary" in data
    assert "task_summary" in data
    assert "tool_summary" in data
    assert "audit_summary" in data
    assert "memory_summary" in data
    assert "skills_summary" in data
    assert "session_count" in data["memory_summary"]
    assert "message_count" in data["memory_summary"]
    assert "skill_count" in data["skills_summary"]
    assert "skill_names" in data["skills_summary"]


def test_reflection_structured_result_no_empty_answer():
    engine = SelfCheckEngine()
    result = engine.check({
        "success": True,
        "formatted_result": {"summary": "查询结果：GMV 为 10000 元"},
    })
    assert not any("empty" in i.lower() or "no presentable" in i.lower() for i in result.issues)


def test_reflection_waiting_approval_not_marked_failed():
    engine = SelfCheckEngine()
    result = engine.check({
        "success": False,
        "requires_approval": True,
        "approval_id": "apr_001",
        "status": "waiting_approval",
        "answer": "需要审批",
    })
    assert "task_result.success is false" not in result.issues
    assert not any("waiting_approval" in i and "failed" in i for i in result.issues)


def test_session_id_memory_cross_task():
    reset_runtime_for_test()
    from app.main import get_kernel, get_memory
    kernel = get_kernel()
    memory = get_memory()

    task1 = TaskRun(task_id="st_1", query="今日GMV")
    asyncio.run(kernel.run_with_options(task1, mode="keyword", session_id="shared_session"))

    task2 = TaskRun(task_id="st_2", query="订单数量")
    asyncio.run(kernel.run_with_options(task2, mode="keyword", session_id="shared_session"))

    ctx = memory.get_context("shared_session")
    assert ctx["message_count"] >= 4
    reset_runtime_for_test()


def test_no_session_id_old_behavior():
    reset_runtime_for_test()
    from app.main import get_kernel, get_memory
    kernel = get_kernel()
    memory = get_memory()

    task = TaskRun(task_id="old_behavior_1", query="今日GMV")
    asyncio.run(kernel.run(task))

    msgs = memory.get_messages(task.task_id)
    assert len(msgs) >= 2
    reset_runtime_for_test()


def test_get_skill_registry_singleton():
    reset_runtime_for_test()
    from app.main import get_skill_registry
    r1 = get_skill_registry()
    r2 = get_skill_registry()
    assert r1 is r2
    reset_runtime_for_test()


def test_skills_match_no_regression():
    registry = SkillRegistry()
    matched = registry.match("今日GMV")
    assert len(matched) >= 1
    assert any(s.name == "ops_metrics_skill" for s in matched)


def test_sqlite_metrics_store_time_filter():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "time_filter.sqlite")
        store = SQLiteMetricsStore(db_path=db_path)
        store.append_task_metric("t1", "keyword", "completed", timestamp="2025-01-01T10:00:00+00:00")
        store.append_task_metric("t2", "keyword", "completed", timestamp="2025-06-01T10:00:00+00:00")

        s = store.summary(start_time="2025-03-01T00:00:00+00:00")
        assert s["task_count"] == 1

        s2 = store.summary(end_time="2025-03-01T00:00:00+00:00")
        assert s2["task_count"] == 1

        s3 = store.summary(
            start_time="2025-01-01T00:00:00+00:00",
            end_time="2025-12-31T23:59:59+00:00",
        )
        assert s3["task_count"] == 2
