from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.agent.nl2sql.provider import create_provider
from app.core.config import settings
from app.harness.llm.acceptance import summarize_llm_acceptance
from app.harness.llm.budget import get_llm_budget_manager
from app.harness.llm.cache import build_judge_cache_key, get_llm_result_cache


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

        if judge_input.rubric and judge_input.actual in judge_input.rubric:
            return JudgeResult(
                score=1.0,
                passed=True,
                reasoning=f"actual matches rubric: {judge_input.rubric}",
                judge_provider="fake",
            )

        if judge_input.expected == "blocked" and judge_input.actual in {"blocked", "failed"}:
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
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        self._provider = provider or "litellm"
        self._fallback_to_fake = settings.judge_fallback_to_fake if fallback_to_fake is None else fallback_to_fake
        self._fallback_judge = fallback_judge or FakeJudge()
        self._model = settings.judge_model if model is None else model
        default_judge_base_url = settings.judge_base_url or settings.llm_base_url
        self._base_url = default_judge_base_url if base_url is None else base_url
        self._timeout_seconds = settings.judge_timeout_seconds if timeout_seconds is None else timeout_seconds
        self._max_retries = settings.judge_max_retries if max_retries is None else max_retries
        self._retry_backoff_seconds = (
            settings.judge_retry_backoff_seconds
            if retry_backoff_seconds is None
            else retry_backoff_seconds
        )
        self._budget_manager = get_llm_budget_manager()
        self._cache = get_llm_result_cache()
        self._last_acceptance_summary: dict[str, Any] | None = None

    @property
    def last_acceptance_summary(self) -> dict[str, Any] | None:
        return self._last_acceptance_summary

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
            "你是评测裁判，请根据输入返回 JSON 对象，不要输出其他文本。\n"
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
        budget_status: dict[str, Any] | None = None,
        error_type: str | None = None,
    ) -> JudgeResult:
        if self._fallback_to_fake:
            fake_result = self._fallback_judge.evaluate(judge_input)
            acceptance = summarize_llm_acceptance(
                mode="judge",
                provider=self._provider,
                model=self._model or "",
                fallback_used=True,
                fallback_reason=reason,
                budget_status=budget_status,
                error_type=error_type or "fallback_fake",
                warnings=[reason],
                real_call_attempted=not str(reason).startswith("budget_blocked"),
            )
            self._last_acceptance_summary = acceptance.to_dict()
            return fake_result.model_copy(
                update={
                    "judge_provider": "fallback_fake",
                    "fallback_used": True,
                    "fallback_reason": reason,
                    "provider_metadata": {"acceptance_summary": self._last_acceptance_summary},
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost": 0.0,
                    "confidence": self._clamp_01(fake_result.score),
                }
            )

        acceptance = summarize_llm_acceptance(
            mode="judge",
            provider=self._provider,
            model=self._model or "",
            fallback_used=False,
            fallback_reason=reason,
            budget_status=budget_status,
            error_type=error_type or "llm_unavailable",
            warnings=[reason],
            real_call_attempted=not str(reason).startswith("budget_blocked"),
        )
        self._last_acceptance_summary = acceptance.to_dict()
        return JudgeResult(
            score=0.0,
            passed=False,
            reasoning=f"LLM judge unavailable: {reason}",
            judge_provider="llm_unavailable",
            fallback_used=False,
            fallback_reason=reason,
            provider_metadata={"acceptance_summary": self._last_acceptance_summary},
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
        self._last_acceptance_summary = None
        if self._provider == "fake":
            return self._fallback_judge.evaluate(judge_input)

        budget_status = self._budget_manager.check_budget(
            mode="judge",
            provider=self._provider,
            model=self._model or "",
            estimated_cost=0.0,
        )
        if not budget_status.get("allowed", True):
            return self._fallback_or_unavailable(
                judge_input=judge_input,
                reason=str(budget_status.get("reason", "budget_blocked")),
                budget_status=budget_status,
                error_type="budget_blocked",
            )

        cache_key = build_judge_cache_key(
            case_id=judge_input.case_id,
            expected=judge_input.expected,
            actual=judge_input.actual,
            rubric=judge_input.rubric,
            provider=self._provider,
            model=self._model or "",
        )
        cached_result = self._cache.get(cache_key)
        if cached_result is not None:
            cached = dict(cached_result)
            provider_metadata = dict(cached.get("provider_metadata") or {})
            provider_metadata.update(
                {
                    "cache_hit": True,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                }
            )
            acceptance = summarize_llm_acceptance(
                mode="judge",
                provider=self._provider,
                model=self._model or "",
                provider_metadata=provider_metadata,
                fallback_used=bool(cached.get("fallback_used", False)),
                fallback_reason=str(cached.get("fallback_reason", "")),
                budget_status=budget_status,
                warnings=[],
                error_type="",
                real_call_attempted=False,
            )
            self._last_acceptance_summary = acceptance.to_dict()
            return JudgeResult(
                score=self._clamp_01(float(cached.get("score", 0.0))),
                passed=bool(cached.get("passed", False)),
                reasoning=str(cached.get("reasoning", "")),
                judge_provider=str(cached.get("judge_provider", self._provider)),
                fallback_used=bool(cached.get("fallback_used", False)),
                fallback_reason=str(cached.get("fallback_reason", "")),
                provider_metadata=provider_metadata | {"acceptance_summary": self._last_acceptance_summary},
                prompt_tokens=0,
                completion_tokens=0,
                cost=0.0,
                confidence=self._clamp_01(float(cached.get("confidence", 0.0))),
            )

        try:
            provider = create_provider(
                self._provider,
                model=self._model or None,
                base_url=self._base_url or None,
                timeout_seconds=self._timeout_seconds,
                max_retries=self._max_retries,
                retry_backoff_seconds=self._retry_backoff_seconds,
                temperature=settings.llm_temperature,
            )
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
            acceptance = summarize_llm_acceptance(
                mode="judge",
                provider=self._provider,
                model=self._model or provider_metadata.get("model", ""),
                provider_metadata=provider_metadata,
                fallback_used=False,
                fallback_reason="",
                budget_status=budget_status,
                warnings=[],
                error_type="",
                real_call_attempted=True,
            )
            self._last_acceptance_summary = acceptance.to_dict()
            result = JudgeResult(
                score=score,
                passed=passed,
                reasoning=reasoning,
                judge_provider=self._provider,
                fallback_used=False,
                fallback_reason="",
                provider_metadata=provider_metadata | {"acceptance_summary": self._last_acceptance_summary},
                prompt_tokens=metadata.prompt_tokens,
                completion_tokens=metadata.completion_tokens,
                cost=metadata.cost,
                confidence=confidence,
            )
            self._budget_manager.record_usage(
                mode="judge",
                provider=self._provider,
                model=self._model or provider_metadata.get("model", ""),
                prompt_tokens=metadata.prompt_tokens,
                completion_tokens=metadata.completion_tokens,
                cost=metadata.cost,
            )
            self._cache.set(cache_key, result.model_dump())
            return result
        except Exception as exc:
            return self._fallback_or_unavailable(
                judge_input=judge_input,
                reason=str(exc),
                budget_status=budget_status,
                error_type=type(exc).__name__,
            )
