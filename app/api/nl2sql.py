from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.nl2sql.provider import ProviderConfigError, UnknownProviderError
from app.harness.eval.nl2sql_runner import NL2SQLEvalRunner
from app.harness.security.guardrails import GuardrailsEngine
from app.harness.security.injection_guard import PromptInjectionGuard
from app.services.nl2sql_pipeline import NL2SQLPipeline

router = APIRouter(prefix="/nl2sql", tags=["nl2sql"])

_injection_guard = PromptInjectionGuard()
_guardrails = GuardrailsEngine()


def _get_audit_recorder():
    from app.main import get_audit_recorder

    return get_audit_recorder()


def _record_llm_acceptance_event(action: str, payload: dict[str, Any]) -> None:
    summary = dict(payload.get("acceptance_summary") or {})
    if not summary:
        return
    provider_used = str(payload.get("provider_used") or "")
    generator_used = str(payload.get("generator_used") or "")
    if generator_used not in {"llm", "mock_fallback"} and provider_used not in {"litellm", "fake", "mock"}:
        return

    outcome = "success" if summary.get("real_call_succeeded") else "fallback"
    if summary.get("error_type"):
        outcome = "error"

    detail = {
        "request_id": summary.get("request_id", ""),
        "provider": summary.get("provider", ""),
        "model": summary.get("model", ""),
        "real_call_attempted": bool(summary.get("real_call_attempted", False)),
        "real_call_succeeded": bool(summary.get("real_call_succeeded", False)),
        "fallback_used": bool(summary.get("fallback_used", False)),
        "fallback_reason": summary.get("fallback_reason", ""),
        "budget_action": summary.get("budget_action", ""),
        "cache_hit": bool(summary.get("cache_hit", False)),
        "prompt_tokens": int(summary.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(summary.get("completion_tokens", 0) or 0),
        "total_tokens": int(summary.get("total_tokens", 0) or 0),
        "cost": float(summary.get("cost", 0.0) or 0.0),
        "latency_ms": float(summary.get("latency_ms", 0.0) or 0.0),
        "error_type": summary.get("error_type", ""),
        "warnings": list(summary.get("warnings") or []),
    }

    try:
        _get_audit_recorder().record(
            event_type="llm_acceptance",
            action=action,
            outcome=outcome,
            severity="info",
            reason=summary.get("fallback_reason") or summary.get("error_type") or "",
            detail=detail,
        )
    except Exception:
        pass


class PreviewRequest(BaseModel):
    query: str
    generator: str = Field(default="mock", description="生成器类型：mock 或 llm")
    provider: str | None = Field(default=None, description="LLM Provider：fake 或 litellm")
    fallback_to_mock: bool = Field(default=True, description="LLM 失败时是否回退到 mock")


class PreviewResponse(BaseModel):
    selected_tables: list[str]
    fallback: bool
    sql: str
    guard_allowed: bool
    guard_reason: str = ""
    reasoning: str
    confidence: float = 0.0
    generator_used: str = "mock"
    provider_used: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    guardrails: dict | None = None
    provider_metadata: dict | None = None
    budget_status: dict | None = None
    acceptance_summary: dict | None = None


@router.post("/preview", response_model=PreviewResponse)
async def preview_nl2sql(req: PreviewRequest):
    input_guard = _guardrails.check_input(req.query, context={"api": "nl2sql_preview"})
    safe_query = input_guard.get("sanitized_text") or req.query
    finding = _injection_guard.check_text(req.query)
    if finding.action == "block":
        _get_audit_recorder().record(
            event_type="prompt_injection_blocked",
            action="nl2sql_preview",
            outcome="blocked",
            severity=finding.severity,
            reason=finding.reason,
            detail={"query": safe_query, "matched_patterns": finding.matched_patterns},
        )
        return PreviewResponse(
            selected_tables=[],
            fallback=False,
            sql="",
            guard_allowed=False,
            guard_reason=f"prompt injection blocked: {finding.reason}",
            reasoning=finding.reason,
            confidence=0.0,
            generator_used="none",
            warnings=[f"prompt_injection_blocked: {finding.reason}"],
            guardrails={"input": input_guard},
        )
    return _generate_nl2sql_result(req, safe_query=safe_query, input_guard=input_guard)


class EvalRequest(BaseModel):
    generator: str = Field(default="mock", description="生成器类型：mock 或 llm")
    provider: str | None = Field(default=None, description="LLM Provider：fake 或 litellm")
    fallback_to_mock: bool = Field(default=True, description="LLM 失败时是否回退到 mock")
    execute_sql: bool = Field(default=False, description="是否执行 SQL 验证")


class EvalResponse(BaseModel):
    total: int
    passed: int
    failed: int
    accuracy: float
    generator_used: str = "mock"
    provider_used: str | None = None
    fallback_count: int = 0
    execution_passed: int = 0
    execution_failed: int = 0
    failures: list[dict]


@router.post("/eval", response_model=EvalResponse)
async def run_nl2sql_eval(req: EvalRequest = EvalRequest()):
    try:
        runner = NL2SQLEvalRunner(
            generator=req.generator,
            provider=req.provider,
            fallback_to_mock=req.fallback_to_mock,
            execute_sql=req.execute_sql,
        )
    except (UnknownProviderError, ProviderConfigError) as exc:
        return EvalResponse(
            total=0,
            passed=0,
            failed=0,
            accuracy=0.0,
            generator_used=req.generator,
            provider_used=req.provider,
            fallback_count=0,
            failures=[{"case_id": "__provider_error__", "input": "", "reason": str(exc)}],
        )
    stats = runner.run()
    return EvalResponse(
        total=stats.total,
        passed=stats.passed,
        failed=stats.failed,
        accuracy=stats.accuracy,
        generator_used=stats.generator_used,
        provider_used=stats.provider_used,
        fallback_count=stats.fallback_count,
        execution_passed=stats.execution_passed,
        execution_failed=stats.execution_failed,
        failures=[f.model_dump() for f in stats.failures],
    )


class ExecuteRequest(BaseModel):
    query: str
    generator: str = Field(default="mock", description="生成器类型：mock 或 llm")
    provider: str | None = Field(default=None, description="LLM Provider：fake 或 litellm")
    fallback_to_mock: bool = Field(default=True, description="LLM 失败时是否回退到 mock")


class ExecuteResponse(BaseModel):
    selected_tables: list[str]
    fallback: bool
    sql: str
    guard_allowed: bool
    guard_reason: str = ""
    reasoning: str
    confidence: float = 0.0
    generator_used: str = "mock"
    provider_used: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    execution: dict | None = None
    formatted_result: dict | None = None
    chart_spec: dict | None = None
    guardrails: dict | None = None
    provider_metadata: dict | None = None
    budget_status: dict | None = None
    acceptance_summary: dict | None = None


def _generate_nl2sql_result(req: PreviewRequest, safe_query: str | None = None, input_guard: dict | None = None):
    pipeline = NL2SQLPipeline()
    result = pipeline.preview(
        query=safe_query or req.query,
        generator=req.generator,
        provider=req.provider,
        fallback_to_mock=req.fallback_to_mock,
    )
    merged_guardrails = result.get("guardrails") or {}
    if input_guard is not None:
        merged_guardrails = {"input": input_guard, **merged_guardrails}
    _record_llm_acceptance_event("nl2sql_preview", result)
    return PreviewResponse(
        selected_tables=result["selected_tables"],
        fallback=result["fallback"],
        sql=result["sql"],
        guard_allowed=result["guard_allowed"],
        guard_reason=result["guard_reason"],
        reasoning=result["reasoning"],
        confidence=result["confidence"],
        generator_used=result["generator_used"],
        provider_used=result["provider_used"],
        fallback_used=result["fallback_used"],
        fallback_reason=result["fallback_reason"],
        warnings=result["warnings"],
        guardrails=merged_guardrails,
        provider_metadata=result.get("provider_metadata"),
        budget_status=result.get("budget_status"),
        acceptance_summary=result.get("acceptance_summary"),
    )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_nl2sql(req: ExecuteRequest):
    input_guard = _guardrails.check_input(req.query, context={"api": "nl2sql_execute"})
    safe_query = input_guard.get("sanitized_text") or req.query
    finding = _injection_guard.check_text(req.query)
    if finding.action == "block":
        _get_audit_recorder().record(
            event_type="prompt_injection_blocked",
            action="nl2sql_execute",
            outcome="blocked",
            severity=finding.severity,
            reason=finding.reason,
            detail={"query": safe_query, "matched_patterns": finding.matched_patterns},
        )
        return ExecuteResponse(
            selected_tables=[],
            fallback=False,
            sql="",
            guard_allowed=False,
            guard_reason=f"prompt injection blocked: {finding.reason}",
            reasoning=finding.reason,
            confidence=0.0,
            generator_used="none",
            warnings=[f"prompt_injection_blocked: {finding.reason}"],
            guardrails={"input": input_guard},
        )
    pipeline = NL2SQLPipeline()
    result = pipeline.run(
        query=safe_query,
        generator=req.generator,
        provider=req.provider,
        fallback_to_mock=req.fallback_to_mock,
    )
    merged_guardrails = result.get("guardrails") or {}
    merged_guardrails = {"input": input_guard, **merged_guardrails}
    _record_llm_acceptance_event("nl2sql_execute", result)
    return ExecuteResponse(
        selected_tables=result["selected_tables"],
        fallback=not result["guard_allowed"],
        sql=result["sql"],
        guard_allowed=result["guard_allowed"],
        guard_reason=result["guard_reason"],
        reasoning=result["reasoning"],
        confidence=result["confidence"],
        generator_used=result["generator_used"],
        provider_used=result["provider_used"],
        fallback_used=result["fallback_used"],
        fallback_reason=result["fallback_reason"],
        warnings=result["warnings"],
        execution=result["execution"],
        formatted_result=result["formatted_result"],
        chart_spec=result["chart_spec"],
        guardrails=merged_guardrails,
        provider_metadata=result.get("provider_metadata"),
        budget_status=result.get("budget_status"),
        acceptance_summary=result.get("acceptance_summary"),
    )
