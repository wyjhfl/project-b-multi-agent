from __future__ import annotations

from pydantic import BaseModel, Field


class TrajectoryExpectation(BaseModel):
    expected_mode: str | None = None
    expected_roles: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    expected_events: list[str] = Field(default_factory=list)
    approval_required: bool | None = None
    max_steps: int | None = None
    allow_fallback: bool = True


class TrajectoryEvalResult(BaseModel):
    passed: bool = True
    score: float = 1.0
    issues: list[str] = Field(default_factory=list)
    matched_roles: list[str] = Field(default_factory=list)
    matched_tools: list[str] = Field(default_factory=list)
    matched_events: list[str] = Field(default_factory=list)


def extract_tool_names(obj: object) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "tool_name" and isinstance(value, str):
                found.add(value)
            else:
                found.update(extract_tool_names(value))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found.update(extract_tool_names(item))
    return found


class TrajectoryEvaluator:

    def evaluate(
        self,
        trace_events: list[dict],
        expectation: TrajectoryExpectation,
    ) -> TrajectoryEvalResult:
        issues: list[str] = []
        matched_roles: list[str] = []
        matched_tools: list[str] = []
        matched_events: list[str] = []
        score_parts: list[float] = []
        total_checks = 0

        event_types = [e.get("event_type", "") for e in trace_events]
        details = [e.get("detail", {}) for e in trace_events]

        if expectation.expected_mode is not None:
            total_checks += 1
            mode_found = False
            for d in details:
                if d.get("selected_mode") == expectation.expected_mode:
                    mode_found = True
                    break
                if d.get("executed_mode") == expectation.expected_mode:
                    mode_found = True
                    break
            for et in event_types:
                if expectation.expected_mode in et:
                    mode_found = True
                    break
            if mode_found:
                score_parts.append(1.0)
            else:
                if expectation.allow_fallback:
                    fallback_modes = set()
                    for d in details:
                        if d.get("executed_mode"):
                            fallback_modes.add(d["executed_mode"])
                    if fallback_modes:
                        score_parts.append(0.5)
                        issues.append(f"mode 期望 {expectation.expected_mode}，实际 {fallback_modes}（fallback）")
                    else:
                        issues.append(f"critical: mode 期望 {expectation.expected_mode}，未找到")
                        score_parts.append(0.0)
                else:
                    issues.append(f"critical: mode 期望 {expectation.expected_mode}，未找到（不允许 fallback）")
                    score_parts.append(0.0)

        if expectation.expected_roles:
            total_checks += 1
            role_events = set()
            for et in event_types:
                for role in expectation.expected_roles:
                    if role in et:
                        role_events.add(role)
            for d in details:
                for role in expectation.expected_roles:
                    if d.get("action") and role in str(d.get("action", "")):
                        role_events.add(role)
            matched_roles = [r for r in expectation.expected_roles if r in role_events]
            missing_roles = [r for r in expectation.expected_roles if r not in role_events]
            if not missing_roles:
                score_parts.append(1.0)
            else:
                issues.append(f"critical: 缺少角色 {missing_roles}")
                ratio = len(matched_roles) / len(expectation.expected_roles)
                score_parts.append(ratio)

        if expectation.expected_tools:
            total_checks += 1
            tool_names_found: set[str] = set()
            for d in details:
                tool_names_found.update(extract_tool_names(d))
            matched_tools = [t for t in expectation.expected_tools if t in tool_names_found]
            missing_tools = [t for t in expectation.expected_tools if t not in tool_names_found]
            if not missing_tools:
                score_parts.append(1.0)
            else:
                issues.append(f"critical: 缺少工具 {missing_tools}")
                ratio = len(matched_tools) / len(expectation.expected_tools)
                score_parts.append(ratio)

        if expectation.expected_events:
            total_checks += 1
            found_events: set[str] = set()
            for expected_evt in expectation.expected_events:
                for et in event_types:
                    if expected_evt in et:
                        found_events.add(expected_evt)
            matched_events = [e for e in expectation.expected_events if e in found_events]
            missing_events = [e for e in expectation.expected_events if e not in found_events]
            if not missing_events:
                score_parts.append(1.0)
            else:
                issues.append(f"critical: 缺少事件 {missing_events}")
                ratio = len(matched_events) / len(expectation.expected_events)
                score_parts.append(ratio)

        if expectation.approval_required is not None:
            total_checks += 1
            approval_events = [e for e in event_types if "approval" in e]
            if expectation.approval_required:
                if approval_events:
                    score_parts.append(1.0)
                else:
                    issues.append("critical: 期望有审批事件，但未找到")
                    score_parts.append(0.0)
            else:
                if not approval_events:
                    score_parts.append(1.0)
                else:
                    issues.append("critical: 不期望审批事件，但发现了审批相关事件")
                    score_parts.append(0.0)

        if expectation.max_steps is not None:
            total_checks += 1
            step_count = len(trace_events)
            if step_count <= expectation.max_steps:
                score_parts.append(1.0)
            else:
                issues.append(f"critical: 步骤数 {step_count} 超过上限 {expectation.max_steps}")
                score_parts.append(0.0)

        if total_checks == 0:
            score = 1.0
        else:
            score = round(sum(score_parts) / total_checks, 4)

        critical_failures = [i for i in issues if i.startswith("critical:")]
        passed = len(critical_failures) == 0 and score >= 0.8

        return TrajectoryEvalResult(
            passed=passed,
            score=score,
            issues=issues,
            matched_roles=matched_roles,
            matched_tools=matched_tools,
            matched_events=matched_events,
        )
