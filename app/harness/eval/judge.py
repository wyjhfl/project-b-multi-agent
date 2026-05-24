from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class JudgeInput(BaseModel):
    case_id: str
    query: str
    expected: str
    actual: str
    rubric: str = ""


class JudgeResult(BaseModel):
    score: float
    passed: bool
    reasoning: str
    judge_provider: str = "fake"


class BaseJudge(ABC):
    @abstractmethod
    def evaluate(self, judge_input: JudgeInput) -> JudgeResult:
        ...


class FakeJudge(BaseJudge):
    def evaluate(self, judge_input: JudgeInput) -> JudgeResult:
        if judge_input.expected == judge_input.actual:
            return JudgeResult(
                score=1.0,
                passed=True,
                reasoning=f"expected==actual: {judge_input.expected}",
                judge_provider="fake",
            )

        rubric_parts = judge_input.rubric
        if rubric_parts and judge_input.actual in rubric_parts:
            return JudgeResult(
                score=1.0,
                passed=True,
                reasoning=f"actual matches rubric: {rubric_parts}",
                judge_provider="fake",
            )

        if judge_input.expected == "blocked" and judge_input.actual in ("blocked", "failed"):
            return JudgeResult(
                score=0.8,
                passed=True,
                reasoning="expected blocked, actual is blocked-like",
                judge_provider="fake",
            )

        if judge_input.expected == "success" and judge_input.actual == "success":
            return JudgeResult(
                score=1.0,
                passed=True,
                reasoning="both success",
                judge_provider="fake",
            )

        return JudgeResult(
            score=0.0,
            passed=False,
            reasoning=f"mismatch: expected={judge_input.expected} actual={judge_input.actual}",
            judge_provider="fake",
        )


class LLMJudgeProvider(BaseJudge):
    def __init__(self, provider: str | None = None) -> None:
        self._provider = provider or "litellm"

    def evaluate(self, judge_input: JudgeInput) -> JudgeResult:
        return JudgeResult(
            score=0.0,
            passed=False,
            reasoning=f"LLM Judge unavailable: provider={self._provider} not configured. Set LITELLM_API_KEY to enable.",
            judge_provider="llm_unavailable",
        )
