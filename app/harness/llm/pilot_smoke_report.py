from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.harness.llm.pilot_evidence import collect_llm_runtime_evidence_snapshot
from app.harness.llm.pilot_report import (
    PilotReportCase,
    build_pilot_report,
    summarize_base_url,
    write_pilot_report_json,
    write_pilot_report_markdown,
)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "on"}


def resolve_pilot_report_output_dir() -> Path | None:
    value = (os.getenv("REAL_LLM_PILOT_REPORT_DIR", "") or "").strip()
    if not value:
        return None
    return Path(value)


def resolve_smoke_commit() -> str:
    return (
        (os.getenv("REAL_LLM_PILOT_COMMIT", "") or "").strip()
        or (os.getenv("GITHUB_SHA", "") or "").strip()
        or (os.getenv("CI_COMMIT_SHA", "") or "").strip()
        or "unknown"
    )


def _runtime_metrics_snapshot_safe() -> dict[str, Any]:
    try:
        from app.main import get_metrics_recorder

        recorder = get_metrics_recorder()
        runtime = recorder.summary()
        from app.harness.llm.budget import get_llm_budget_manager
        from app.harness.llm.cache import get_llm_result_cache

        runtime["llm_budget"] = get_llm_budget_manager().summary()
        runtime["llm_cache"] = get_llm_result_cache().stats()
        return collect_llm_runtime_evidence_snapshot(runtime)
    except Exception:
        return {"llm_budget": {"enabled": False}, "llm_cache": {"enabled": False}, "runtime_metric_keys": []}


def _latest_llm_acceptance_event(event_type: str, request_id: str) -> dict[str, Any]:
    if not request_id:
        return {"audit_event_id": "", "audit_event_type": event_type, "log_request_id": ""}
    try:
        from app.main import get_audit_store

        events = get_audit_store().query_events(event_type=event_type, limit=50)
        for event in events:
            detail = dict(event.get("detail") or {})
            if str(detail.get("request_id") or "") == request_id:
                return {
                    "audit_event_id": event.get("event_id", ""),
                    "audit_event_type": event.get("event_type", ""),
                    "log_request_id": request_id,
                }
    except Exception:
        return {"audit_event_id": "", "audit_event_type": event_type, "log_request_id": request_id}
    return {"audit_event_id": "", "audit_event_type": event_type, "log_request_id": request_id}


def build_nl2sql_pilot_case(payload: dict[str, Any]) -> PilotReportCase:
    summary = dict(payload.get("acceptance_summary") or {})
    provider_metadata = dict(payload.get("provider_metadata") or {})
    fallback_reason = str(
        payload.get("fallback_reason")
        or summary.get("fallback_reason")
        or summary.get("error_type")
        or "unknown"
    )
    request_id = str(summary.get("request_id") or provider_metadata.get("request_id") or "")
    provider_name = str(summary.get("provider") or payload.get("provider_used") or "")
    model_name = str(summary.get("model") or provider_metadata.get("model") or settings.llm_model or "")
    base_url = settings.real_llm_base_url or settings.llm_base_url or ""
    api_key_env = (os.getenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY") or "OPENAI_API_KEY").strip()
    api_key_present = bool(os.getenv(api_key_env, ""))
    evidence_links = _latest_llm_acceptance_event("llm_acceptance", request_id)
    metrics_snapshot = _runtime_metrics_snapshot_safe()

    return PilotReportCase(
        scenario="nl2sql_preview",
        endpoint="/nl2sql/preview",
        request_id=request_id,
        provider=provider_name,
        model=model_name,
        base_url_summary=summarize_base_url(base_url),
        api_key_env=api_key_env,
        api_key_present=api_key_present,
        real_call_attempted=_normalize_bool(summary.get("real_call_attempted")),
        real_call_succeeded=_normalize_bool(summary.get("real_call_succeeded")),
        fallback_used=_normalize_bool(payload.get("fallback_used") or summary.get("fallback_used")),
        fallback_reason=fallback_reason,
        budget_action=str(summary.get("budget_action") or ""),
        cache_hit=_normalize_bool(summary.get("cache_hit")),
        latency_ms=float(summary.get("latency_ms") or provider_metadata.get("latency_ms") or 0.0),
        prompt_tokens=int(summary.get("prompt_tokens") or provider_metadata.get("prompt_tokens") or 0),
        completion_tokens=int(summary.get("completion_tokens") or provider_metadata.get("completion_tokens") or 0),
        total_tokens=int(summary.get("total_tokens") or provider_metadata.get("total_tokens") or 0),
        cost=float(summary.get("cost") or provider_metadata.get("cost") or 0.0),
        error_type=str(summary.get("error_type") or ""),
        outcome=(
            "success"
            if _normalize_bool(summary.get("real_call_succeeded"))
            else ("fallback" if _normalize_bool(payload.get("fallback_used") or summary.get("fallback_used")) else "failed")
        ),
        warnings=list(payload.get("warnings") or summary.get("warnings") or []),
        evidence_links=evidence_links,
        observability=metrics_snapshot,
        evidence_notes=["nl2sql_pilot_evidence", "controlled_pilot"],
        detail={
            "generator_used": payload.get("generator_used"),
            "provider_used": payload.get("provider_used"),
            "guard_allowed": payload.get("guard_allowed"),
            "fallback_reason": fallback_reason,
            "query": "[REDACTED_PROMPT]",
            "acceptance_summary": summary,
        },
    )


def build_judge_pilot_case(result: Any) -> PilotReportCase:
    provider_metadata = dict(getattr(result, "provider_metadata", None) or {})
    summary = dict(provider_metadata.get("acceptance_summary") or {})
    request_id = str(summary.get("request_id") or provider_metadata.get("request_id") or "")
    provider_name = str(summary.get("provider") or getattr(result, "judge_provider", "") or "")
    model_name = str(summary.get("model") or provider_metadata.get("model") or settings.judge_model or "")
    base_url = settings.real_llm_base_url or settings.judge_base_url or settings.llm_base_url or ""
    api_key_env = (os.getenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY") or "OPENAI_API_KEY").strip()
    api_key_present = bool(os.getenv(api_key_env, ""))
    fallback_reason = str(
        getattr(result, "fallback_reason", "")
        or summary.get("fallback_reason")
        or summary.get("error_type")
        or "unknown"
    )
    evidence_links = _latest_llm_acceptance_event("llm_acceptance", request_id)
    metrics_snapshot = _runtime_metrics_snapshot_safe()

    return PilotReportCase(
        scenario="llm_judge",
        endpoint="judge:evaluate",
        request_id=request_id,
        provider=provider_name,
        model=model_name,
        base_url_summary=summarize_base_url(base_url),
        api_key_env=api_key_env,
        api_key_present=api_key_present,
        real_call_attempted=_normalize_bool(summary.get("real_call_attempted")),
        real_call_succeeded=_normalize_bool(summary.get("real_call_succeeded")),
        fallback_used=_normalize_bool(getattr(result, "fallback_used", False) or summary.get("fallback_used")),
        fallback_reason=fallback_reason,
        budget_action=str(summary.get("budget_action") or ""),
        cache_hit=_normalize_bool(summary.get("cache_hit")),
        latency_ms=float(summary.get("latency_ms") or provider_metadata.get("latency_ms") or 0.0),
        prompt_tokens=int(summary.get("prompt_tokens") or provider_metadata.get("prompt_tokens") or 0),
        completion_tokens=int(summary.get("completion_tokens") or provider_metadata.get("completion_tokens") or 0),
        total_tokens=int(summary.get("total_tokens") or provider_metadata.get("total_tokens") or 0),
        cost=float(summary.get("cost") or provider_metadata.get("cost") or 0.0),
        error_type=str(summary.get("error_type") or provider_metadata.get("error_type") or ""),
        outcome=(
            "success"
            if _normalize_bool(summary.get("real_call_succeeded"))
            else ("fallback" if _normalize_bool(getattr(result, "fallback_used", False) or summary.get("fallback_used")) else "failed")
        ),
        warnings=list(summary.get("warnings") or []),
        evidence_links=evidence_links,
        observability=metrics_snapshot,
        evidence_notes=["judge_pilot_evidence", "controlled_pilot"],
        detail={
            "judge_provider": getattr(result, "judge_provider", ""),
            "score": float(getattr(result, "score", 0.0)),
            "passed": bool(getattr(result, "passed", False)),
            "confidence": float(getattr(result, "confidence", 0.0)),
            "fallback_reason": fallback_reason,
            "query": "[REDACTED_PROMPT]",
            "expected": "[REDACTED_PROMPT]",
            "actual": "[REDACTED_PROMPT]",
            "rubric": "[REDACTED_PROMPT]",
            "acceptance_summary": summary,
        },
    )


def write_pilot_report_for_case(case: PilotReportCase, *, report_prefix: str) -> dict[str, str]:
    report = build_pilot_report(
        cases=[case],
        commit=resolve_smoke_commit(),
        environment=settings.app_env,
        report_id=f"{report_prefix}-{case.request_id or case.scenario}",
    )
    output_dir = resolve_pilot_report_output_dir()
    json_path = write_pilot_report_json(report, output_dir=output_dir)
    markdown_path = write_pilot_report_markdown(report, output_dir=output_dir)
    return {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(json_path.parent),
    }
