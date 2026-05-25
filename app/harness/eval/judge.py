from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any

from pydantic import BaseModel

from app.agent.nl2sql.provider import create_provider
from app.core.config import settings


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
    fallback_used: bool = False
    fallback_reason: str = ""
    provider_metadata: dict[str, Any] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    confidence: float = 0.0


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
    def __init__(
        self,
        provider: str | None = None,
        fallback_to_fake: bool | None = None,
        fallback_judge: BaseJudge | None = None,
    ) -> None:
        self._provider = provider or "litellm"
        self._fallback_to_fake = settings.judge_fallback_to_fake if fallback_to_fake is None else fallback_to_fake
        self._fallback_judge = fallback_judge or FakeJudge()

    @staticmethod
    def _clamp_01(value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError("judge_json_not_object")
            return payload
        except json.JSONDecodeError:
            pass

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            candidate = stripped[start : end + 1]
            payload = json.loads(candidate)
            if not isinstance(payload, dict):
                raise ValueError("judge_json_not_object")
            return payload
        raise ValueError("judge_invalid_json")

    @staticmethod
    def _build_prompt(judge_input: JudgeInput) -> str:
        return (
            "你是评测裁判，请根据输入给出 JSON 对象，不要输出其他文本。\n"
            "JSON 字段要求：score(0~1), passed(bool), reasoning(string), confidence(0~1)。\n"
            f"query: {judge_input.query}\n"
            f"expected: {judge_input.expected}\n"
            f"actual: {judge_input.actual}\n"
            f"rubric: {judge_input.rubric}\n"
        )

    def _fallback_or_unavailable(
        self,
        judge_input: JudgeInput,
        reason: str,
    ) -> JudgeResult:
        if self._fallback_to_fake:
            fake_result = self._fallback_judge.evaluate(judge_input)
            return fake_result.model_copy(
                update={
                    "judge_provider": "fallback_fake",
                    "fallback_used": True,
                    "fallback_reason": reason,
                    "provider_metadata": None,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost": 0.0,
                    "confidence": self._clamp_01(fake_result.score),
                }
            )
        return JudgeResult(
            score=0.0,
            passed=False,
            reasoning=f"LLM judge unavailable: {reason}",
            judge_provider="llm_unavailable",
            fallback_used=False,
            fallback_reason=reason,
            provider_metadata=None,
            prompt_tokens=0,
            completion_tokens=0,
            cost=0.0,
            confidence=0.0,
        )

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        raise ValueError("judge_passed_not_bool")

    def evaluate(self, judge_input: JudgeInput) -> JudgeResult:
        try:
            provider = create_provider(self._provider)
            prompt = self._build_prompt(judge_input)
            metadata = provider.generate_with_metadata(prompt)
            payload = self._extract_json_object(metadata.content)

            if "score" not in payload:
                raise ValueError("judge_missing_score")
            score = self._clamp_01(float(payload["score"]))
            confidence_raw = payload.get("confidence", score)
            confidence = self._clamp_01(float(confidence_raw))
            passed = self._parse_bool(payload.get("passed"))
            reasoning = str(payload.get("reasoning", "")).strip() or "LLM judge returned empty reasoning"

            provider_metadata = metadata.to_dict()
            return JudgeResult(
                score=score,
                passed=passed,
                reasoning=reasoning,
                judge_provider=self._provider,
                fallback_used=False,
                fallback_reason="",
                provider_metadata=provider_metadata,
                prompt_tokens=metadata.prompt_tokens,
                completion_tokens=metadata.completion_tokens,
                cost=metadata.cost,
                confidence=confidence,
            )
        except Exception as exc:
            return self._fallback_or_unavailable(judge_input=judge_input, reason=str(exc))
