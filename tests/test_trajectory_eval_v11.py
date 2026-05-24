from __future__ import annotations

from app.harness.eval.trajectory import TrajectoryEvalResult, TrajectoryEvaluator, TrajectoryExpectation, extract_tool_names


def _make_events(event_types: list[str], details: list[dict] | None = None) -> list[dict]:
    if details is None:
        details = [{} for _ in event_types]
    return [{"event_type": et, "detail": d} for et, d in zip(event_types, details)]


class TestTrajectoryEvaluator:

    def setup_method(self):
        self.evaluator = TrajectoryEvaluator()

    def test_all_pass(self):
        events = _make_events(
            ["multi_agent_started", "coordinator_decided", "analyst_planned", "executor_completed", "reviewer_completed"],
            [
                {},
                {"selected_mode": "multitool"},
                {"plan_summary": "need rule_lookup"},
                {"tool_name": "rule_lookup", "success": True},
                {"approved": True},
            ],
        )
        exp = TrajectoryExpectation(
            expected_mode="multitool",
            expected_roles=["coordinator", "analyst", "executor", "reviewer"],
            expected_tools=["rule_lookup"],
            expected_events=["multi_agent_started", "coordinator_decided"],
            approval_required=False,
            max_steps=10,
        )
        result = self.evaluator.evaluate(events, exp)
        assert isinstance(result, TrajectoryEvalResult)
        assert result.passed is True
        assert result.score >= 0.8
        assert "coordinator" in result.matched_roles
        assert "rule_lookup" in result.matched_tools

    def test_missing_role_fails(self):
        events = _make_events(
            ["multi_agent_started", "coordinator_decided"],
            [{}, {"selected_mode": "multitool"}],
        )
        exp = TrajectoryExpectation(
            expected_roles=["coordinator", "analyst", "executor", "reviewer"],
        )
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("critical: 缺少角色" in i for i in result.issues)

    def test_missing_tool_fails(self):
        events = _make_events(
            ["tool_called"],
            [{"tool_name": "get_today_gmv"}],
        )
        exp = TrajectoryExpectation(
            expected_tools=["rule_lookup", "get_refund_rate"],
        )
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("critical: 缺少工具" in i for i in result.issues)

    def test_missing_approval_event_fails(self):
        events = _make_events(["task_started", "task_completed"], [{}, {}])
        exp = TrajectoryExpectation(
            approval_required=True,
        )
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("审批" in i and "critical" in i for i in result.issues)

    def test_max_steps_exceeded_fails(self):
        events = _make_events(
            ["task_started"] + ["tool_called"] * 15,
            [{}] + [{"tool_name": f"tool_{i}"} for i in range(15)],
        )
        exp = TrajectoryExpectation(max_steps=5)
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("critical: 步骤数" in i for i in result.issues)

    def test_mode_mismatch_with_fallback_can_pass(self):
        events = _make_events(
            ["multi_agent_started", "coordinator_decided", "analyst_planned", "executor_completed", "reviewer_completed"],
            [
                {},
                {"selected_mode": "keyword", "executed_mode": "keyword"},
                {"plan_summary": "date lookup"},
                {"success": True, "executed_mode": "keyword"},
                {"approved": True},
            ],
        )
        exp = TrajectoryExpectation(
            expected_mode="nl2sql",
            expected_events=["multi_agent_started", "executor_completed", "reviewer_completed"],
            approval_required=False,
            max_steps=10,
            allow_fallback=True,
        )
        result = self.evaluator.evaluate(events, exp)
        assert any("fallback" in i for i in result.issues)
        assert result.score >= 0.5

    def test_empty_expectation_passes(self):
        events = _make_events(["task_started"], [{}])
        exp = TrajectoryExpectation()
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is True
        assert result.score == 1.0

    def test_approval_not_required_but_found_fails(self):
        events = _make_events(
            ["task_started", "approval_requested", "task_completed"],
            [{}, {"approval_id": "a1"}, {}],
        )
        exp = TrajectoryExpectation(approval_required=False)
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("审批" in i and "critical" in i for i in result.issues)

    def test_no_fallback_mode_strict(self):
        events = _make_events(
            ["coordinator_decided"],
            [{"executed_mode": "keyword"}],
        )
        exp = TrajectoryExpectation(
            expected_mode="nl2sql",
            allow_fallback=False,
        )
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("critical: mode" in i and "不允许 fallback" in i for i in result.issues)

    def test_missing_event_fails(self):
        events = _make_events(["multi_agent_started"], [{}])
        exp = TrajectoryExpectation(
            expected_events=["multi_agent_started", "coordinator_decided", "executor_completed"],
        )
        result = self.evaluator.evaluate(events, exp)
        assert result.passed is False
        assert any("critical: 缺少事件" in i for i in result.issues)


class TestExtractToolNames:

    def test_simple_tool_name(self):
        result = extract_tool_names({"tool_name": "get_today_gmv"})
        assert "get_today_gmv" in result

    def test_tool_calls_list(self):
        data = {"tool_calls": [{"tool_name": "rule_lookup"}, {"tool_name": "get_refund_rate"}]}
        result = extract_tool_names(data)
        assert "rule_lookup" in result
        assert "get_refund_rate" in result

    def test_nested_result_tool_calls(self):
        data = {"result": {"tool_calls": [{"tool_name": "date_lookup"}]}}
        result = extract_tool_names(data)
        assert "date_lookup" in result

    def test_deeply_nested(self):
        data = {"outer": {"inner": [{"nested_key": {"tool_name": "deep_tool"}}]}}
        result = extract_tool_names(data)
        assert "deep_tool" in result

    def test_no_tool_name(self):
        data = {"some_key": "some_value", "other": [1, 2, 3]}
        result = extract_tool_names(data)
        assert len(result) == 0

    def test_mixed_structure(self):
        data = {
            "tool_name": "top_level",
            "details": {"tool_calls": [{"tool_name": "nested_1"}]},
            "items": [{"tool_name": "nested_2"}, {"not_a_tool": "skip"}],
        }
        result = extract_tool_names(data)
        assert result == {"top_level", "nested_1", "nested_2"}
