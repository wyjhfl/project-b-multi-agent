from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.harness.context.assembler import ContextAssembler
from app.harness.memory.short_term import ShortTermMemory
from app.harness.metrics.runtime_metrics import RuntimeMetricsRecorder
from app.harness.reflection.self_check import SelfCheckEngine
from app.harness.skills.registry import SkillRegistry
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import TaskRun, TaskStatus

client = TestClient(app)


def test_short_term_memory_add_get():
    mem = ShortTermMemory()
    mem.add_message("s1", "user", "hello")
    mem.add_message("s1", "assistant", "hi there")
    msgs = mem.get_messages("s1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_short_term_memory_limit():
    mem = ShortTermMemory()
    for i in range(20):
        mem.add_message("s1", "user", f"msg_{i}")
    msgs = mem.get_messages("s1", limit=5)
    assert len(msgs) == 5
    assert msgs[0]["content"] == "msg_15"

    msgs_50 = mem.get_messages("s1", limit=100)
    assert len(msgs_50) == 20


def test_short_term_memory_clear():
    mem = ShortTermMemory()
    mem.add_message("s1", "user", "hello")
    mem.clear("s1")
    msgs = mem.get_messages("s1")
    assert len(msgs) == 0


def test_short_term_memory_summarize_truncation():
    mem = ShortTermMemory()
    for i in range(50):
        mem.add_message("s1", "user", f"this is message number {i} with some content")
    summary = mem.summarize("s1", max_chars=100)
    assert len(summary) <= 103
    assert summary.endswith("...")


def test_short_term_memory_summarize_empty():
    mem = ShortTermMemory()
    assert mem.summarize("nonexistent") == ""


def test_context_assembler_memory_context():
    assembler = ContextAssembler()
    task = TaskRun(task_id="test_ctx_1", query="今日GMV")
    ctx = assembler.assemble(task=task, memory_context={"message_count": 3})
    assert ctx.metadata.get("memory_used") is True
    assert ctx.metadata.get("memory_message_count") == 3


def test_context_assembler_no_memory():
    assembler = ContextAssembler()
    task = TaskRun(task_id="test_ctx_2", query="今日GMV")
    ctx = assembler.assemble(task=task)
    assert ctx.metadata.get("memory_used") is None


def test_kernel_writes_memory():
    reset_runtime_for_test()
    from app.main import get_kernel, get_memory
    kernel = get_kernel()
    memory = get_memory()

    task = TaskRun(task_id="mem_test_1", query="今日GMV")
    result = asyncio.run(kernel.run(task))

    msgs = memory.get_messages(task.task_id)
    assert len(msgs) >= 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    reset_runtime_for_test()


def test_skill_registry_register_list_get():
    registry = SkillRegistry()
    skills = registry.list_skills()
    assert len(skills) >= 4

    skill = registry.get_skill("ops_metrics_skill")
    assert skill is not None
    assert "get_today_gmv" in skill.tool_names


def test_skill_registry_match_gmv():
    registry = SkillRegistry()
    matched = registry.match("今日GMV")
    assert len(matched) >= 1
    names = [s.name for s in matched]
    assert "ops_metrics_skill" in names


def test_skill_registry_match_product():
    registry = SkillRegistry()
    matched = registry.match("Top 商品排行")
    assert len(matched) >= 1
    names = [s.name for s in matched]
    assert "product_analysis_skill" in names


def test_skills_api_list():
    resp = client.get("/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 4


def test_skills_api_match():
    resp = client.post("/skills/match", json={"query": "今日GMV"})
    assert resp.status_code == 200
    data = resp.json()
    assert "matched_skills" in data
    assert len(data["matched_skills"]) >= 1


def test_self_check_success_result():
    engine = SelfCheckEngine()
    result = engine.check({"success": True, "answer": "GMV is 10000"})
    assert result.passed is True
    assert result.score == 1.0
    assert len(result.issues) == 0


def test_self_check_failed_result():
    engine = SelfCheckEngine()
    result = engine.check({"success": False, "answer": "查询失败"})
    assert result.passed is False
    assert "task_result.success is false" in result.issues


def test_self_check_requires_approval_no_id():
    engine = SelfCheckEngine()
    result = engine.check({"success": False, "requires_approval": True, "answer": "需要审批"})
    assert result.passed is False
    assert any("approval_id" in i for i in result.issues)


def test_self_check_injection_blocked_but_success():
    engine = SelfCheckEngine()
    result = engine.check(
        {"success": True, "answer": "ok"},
        trace_events=[{"event_type": "prompt_injection_blocked"}],
    )
    assert result.passed is False
    assert any("injection" in i for i in result.issues)


def test_self_check_tool_failed_but_success():
    engine = SelfCheckEngine()
    result = engine.check(
        {"success": True, "answer": "ok"},
        trace_events=[{"event_type": "tool_called", "detail": {"success": False}}],
    )
    assert result.passed is False
    assert any("tool_call failed" in i for i in result.issues)


def test_self_check_empty_answer():
    engine = SelfCheckEngine()
    result = engine.check({"success": True, "answer": ""})
    assert result.passed is False
    assert any("presentable" in i or "empty" in i for i in result.issues)


def test_self_check_waiting_approval_not_failed():
    engine = SelfCheckEngine()
    result = engine.check({"success": False, "requires_approval": True, "approval_id": "apr_123", "status": "waiting_approval", "answer": "需要审批"})
    assert not any("waiting_approval" in i and "failed" in i for i in result.issues)


def test_reflection_api():
    resp = client.post("/reflection/check", json={
        "task_result": {"success": True, "answer": "GMV is 10000"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "passed" in data
    assert "score" in data
    assert "issues" in data
    assert "checked_items" in data


def test_kernel_reflection_in_result():
    reset_runtime_for_test()
    from app.main import get_kernel
    kernel = get_kernel()

    task = TaskRun(task_id="reflect_test_1", query="今日GMV")
    result = asyncio.run(
        kernel.run_with_options(task, mode="keyword")
    )

    assert result.result is not None
    reflection = result.result.get("reflection")
    assert reflection is not None
    assert "passed" in reflection
    assert "score" in reflection
    reset_runtime_for_test()


def test_badcase_approval_pending_uses_real_service():
    reset_runtime_for_test()
    from app.main import get_kernel
    get_kernel()
    from app.harness.eval.bad_case_runner import BadCaseRunner
    runner = BadCaseRunner()
    cases = runner.load_cases()
    pending_case = [c for c in cases if c.case_id == "approval_001"][0]
    result = runner._run_case(pending_case, use_judge=False)
    assert result.actual_outcome == "blocked"
    assert result.actual_error_type == "approval_not_approved"
    assert result.trace_task_id != ""
    reset_runtime_for_test()


def test_badcase_approval_payload_tampered_real_error():
    reset_runtime_for_test()
    from app.main import get_kernel
    get_kernel()
    from app.harness.eval.bad_case_runner import BadCaseRunner
    runner = BadCaseRunner()
    cases = runner.load_cases()
    tampered_case = [c for c in cases if c.case_id == "approval_003"][0]
    result = runner._run_case(tampered_case, use_judge=False)
    assert result.actual_outcome == "blocked"
    assert result.actual_error_type == "approval_payload_tampered"
    reset_runtime_for_test()


def test_metrics_summary_reflection_skill_fields():
    recorder = RuntimeMetricsRecorder()
    recorder.reflection_count = 5
    recorder.reflection_failed_count = 1
    recorder.skill_match_count = 3
    s = recorder.summary()
    assert s["reflection_count"] == 5
    assert s["reflection_failed_count"] == 1
    assert s["skill_match_count"] == 3


def test_memory_api_get():
    reset_runtime_for_test()
    from app.main import get_memory
    memory = get_memory()
    memory.add_message("test_session", "user", "hello")

    resp = client.get("/memory/test_session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test_session"
    assert len(data["messages"]) >= 1
    reset_runtime_for_test()


def test_memory_api_delete():
    reset_runtime_for_test()
    from app.main import get_memory
    memory = get_memory()
    memory.add_message("del_session", "user", "bye")

    resp = client.delete("/memory/del_session")
    assert resp.status_code == 200
    assert resp.json()["cleared"] is True
    reset_runtime_for_test()
