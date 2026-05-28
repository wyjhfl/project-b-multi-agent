from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.operations import (
    _collect_audit_summary,
    _collect_pilot_report_summary,
    _collect_runtime_metrics_summary,
    _collect_task_approval_summary,
)
from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.core.structured_logging import redact_sensitive_value
from app.harness.llm.pilot_report import REDACTED_PROMPT_PLACEHOLDER, sanitize_pilot_report_payload

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "acceptance_snapshots"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _run_git(args: list[str]) -> str:
    try:
        out = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return out.strip()
    except Exception:
        return ""


def _read_json_url(url: str, timeout: float = 3.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _try_collect_online_summary(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    endpoints = {
        "health": f"{base}/health",
        "deployment_check": f"{base}/deployment/check",
        "operations_summary": f"{base}/operations/summary",
    }
    results: dict[str, Any] = {"status": "ok", "base_url": base, "checks": {}}

    health_url = endpoints["health"]
    try:
        health_data = _read_json_url(health_url)
        results["checks"]["health"] = {"status": "ok", "url": health_url, "data": health_data}
    except Exception as exc:
        reason = "service_unavailable"
        if isinstance(exc, URLError):
            reason = "service_unavailable"
        results["status"] = "skipped"
        results["reason"] = reason
        results["checks"]["health"] = {"status": "skipped", "url": health_url, "error": str(exc)}
        return results

    for key in ("deployment_check", "operations_summary"):
        url = endpoints[key]
        try:
            data = _read_json_url(url)
            results["checks"][key] = {"status": "ok", "url": url, "data": data}
        except Exception as exc:
            results["status"] = "partial"
            results["checks"][key] = {"status": "failed", "url": url, "error": str(exc)}
    return results


def _build_health_summary_offline() -> dict[str, Any]:
    from app.main import health_check

    health = asyncio.run(health_check())
    return {
        "status": health.get("status", ""),
        "service": health.get("service", ""),
        "version": health.get("version", ""),
        "storage_backend": health.get("storage_backend", ""),
        "auth_enabled": bool(health.get("auth_enabled", False)),
        "rbac_enabled": bool(health.get("rbac_enabled", False)),
        "redis": health.get("redis"),
    }


def _build_deployment_summary_offline() -> dict[str, Any]:
    check = run_deployment_checks().model_dump()
    return {
        "ok": bool(check.get("ok", False)),
        "environment": check.get("environment", ""),
        "error_count": len(check.get("errors", [])),
        "warning_count": len(check.get("warnings", [])),
        "errors": check.get("errors", []),
        "warnings": check.get("warnings", []),
    }


def _collect_demo_evidence_paths() -> dict[str, Any]:
    entries = {
        "demo_script": "scripts/demo_e2e.ps1",
        "demo_seed_script": "scripts/demo_seed_data.py",
        "demo_runbook": "docs/demo_e2e_runbook_v31.md",
        "troubleshooting_runbook": "docs/operations_troubleshooting_index_v31.md",
        "backup_restore_checklist": "docs/backup_restore_checklist_v31.md",
        "pilot_report_dir": "docs/reports/real_llm_pilot",
    }
    with_exists = {
        key: {"path": rel_path, "exists": (ROOT_DIR / rel_path).exists()}
        for key, rel_path in entries.items()
    }
    return with_exists


def _summarize_operations_summary(
    runtime_metrics: dict[str, Any],
    task_approval: dict[str, Any],
    audit: dict[str, Any],
    pilot_reports: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_metrics": {
            "total_task_count": runtime_metrics.get("total_task_count", 0),
            "total_tool_call_count": runtime_metrics.get("total_tool_call_count", 0),
            "total_prompt_tokens": runtime_metrics.get("total_prompt_tokens", 0),
            "total_completion_tokens": runtime_metrics.get("total_completion_tokens", 0),
            "total_cost": runtime_metrics.get("total_cost", 0.0),
        },
        "task_approval": {
            "task_count": task_approval.get("task_count", 0),
            "approval_count": task_approval.get("approval_count", 0),
            "pending_approval_count": task_approval.get("pending_approval_count", 0),
            "task_status_counts": task_approval.get("task_status_counts", {}),
        },
        "audit": {
            "event_count": audit.get("event_count", 0),
            "recent_events": audit.get("recent_events", [])[:5],
        },
        "pilot_reports": pilot_reports,
    }


_PROMPT_KEY_MARKERS = ("prompt", "query", "raw_prompt", "sql_prompt", "messages", "input")
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "jwt",
    "database_url",
    "redis_url",
    "client_secret",
)
_SAFE_TOKEN_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "total_prompt_tokens",
    "total_completion_tokens",
    "token_usage_count",
}
_EVIDENCE_SAFE_KEYS = _SAFE_TOKEN_KEYS | {
    "cost",
    "total_cost",
    "request_id",
    "cache_hit",
    "budget_action",
    "fallback_reason",
    "latency_ms",
    "status",
    "outcome",
}


def _sanitize_key_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if key_lower in _EVIDENCE_SAFE_KEYS:
        return _sanitize_snapshot_payload(value)
    if any(marker in key_lower for marker in _PROMPT_KEY_MARKERS):
        return REDACTED_PROMPT_PLACEHOLDER
    if any(marker in key_lower for marker in _SENSITIVE_KEY_MARKERS) and key_lower not in _SAFE_TOKEN_KEYS:
        return redact_sensitive_value(value)
    return _sanitize_snapshot_payload(value)


def _sanitize_snapshot_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            sanitized[key_text] = _sanitize_key_value(key_text, value)
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_snapshot_payload(item) for item in payload]
    return sanitize_pilot_report_payload(payload)


def _build_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Snapshot（Read Only）",
        "",
        f"- generated_at: {snapshot.get('generated_at', '')}",
        f"- snapshot_id: {snapshot.get('snapshot_id', '')}",
        f"- commit: {snapshot.get('commit', '')}",
        f"- version: {snapshot.get('version', '')}",
        f"- environment: {snapshot.get('environment', {}).get('app_env', '')}",
        f"- status: {snapshot.get('status', '')}",
        "",
        "## Health Summary",
        f"- status: {snapshot.get('health_summary', {}).get('status', '')}",
        f"- service: {snapshot.get('health_summary', {}).get('service', '')}",
        f"- version: {snapshot.get('health_summary', {}).get('version', '')}",
        "",
        "## Deployment Summary",
        f"- ok: {snapshot.get('deployment_summary', {}).get('ok', False)}",
        f"- error_count: {snapshot.get('deployment_summary', {}).get('error_count', 0)}",
        f"- warning_count: {snapshot.get('deployment_summary', {}).get('warning_count', 0)}",
        "",
        "## Operations Summary（Sanitized）",
        f"- total_task_count: {snapshot.get('operations_summary', {}).get('runtime_metrics', {}).get('total_task_count', 0)}",
        f"- total_tool_call_count: {snapshot.get('operations_summary', {}).get('runtime_metrics', {}).get('total_tool_call_count', 0)}",
        f"- total_cost: {snapshot.get('operations_summary', {}).get('runtime_metrics', {}).get('total_cost', 0)}",
        f"- audit_event_count: {snapshot.get('operations_summary', {}).get('audit', {}).get('event_count', 0)}",
        f"- pilot_reports_total: {snapshot.get('operations_summary', {}).get('pilot_reports', {}).get('total_reports', 0)}",
        "",
        "## Demo Evidence Paths",
    ]
    for key, value in (snapshot.get("demo_evidence_paths") or {}).items():
        if isinstance(value, dict):
            lines.append(f"- {key}: {value.get('path', '')} (exists={value.get('exists', False)})")

    lines.extend(
        [
            "",
            "## Skipped / Limitations",
            f"- skipped: {json.dumps(snapshot.get('skipped', []), ensure_ascii=False)}",
            f"- limitations: {json.dumps(snapshot.get('limitations', []), ensure_ascii=False)}",
            "",
            "## Boundary Declarations",
            "- not public production approval",
            "- not real LLM production acceptance",
            "- no raw prompt / no secrets",
            "",
        ]
    )
    return "\n".join(lines)


def build_acceptance_snapshot(
    *,
    output_dir: str | Path | None = None,
    base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit and commit != "unknown" else "unknown"
    snapshot_id = f"acceptance-{generated_at.replace(':', '-').replace('+', '_')}-{short_commit}"

    runtime_metrics = _collect_runtime_metrics_summary()
    task_approval = _collect_task_approval_summary()
    audit = _collect_audit_summary()
    pilot_reports = _collect_pilot_report_summary()
    online = _try_collect_online_summary(base_url)

    skipped: list[dict[str, Any]] = []
    status = "completed"
    if online.get("status") == "skipped":
        status = "completed_with_skipped_online_checks"
        skipped.append(
            {
                "check": "online_endpoints",
                "reason": online.get("reason", "service_unavailable"),
                "detail": "service not available, offline snapshot generated",
            }
        )
    elif online.get("status") == "partial":
        status = "completed_with_partial_online_checks"
        skipped.append({"check": "online_endpoints", "reason": "partial_failure"})

    payload = {
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "status": status,
        "commit": commit,
        "version": "3.1.0",
        "environment": {
            "app_env": settings.app_env,
            "mode": "fake_offline_default",
            "real_llm_acceptance_enabled": bool(settings.real_llm_acceptance_enabled),
            "real_llm_smoke_enabled": bool(settings.real_llm_smoke_enabled),
            "mcp_mode": settings.mcp_mode,
        },
        "health_summary": _build_health_summary_offline(),
        "deployment_summary": _build_deployment_summary_offline(),
        "operations_summary": _summarize_operations_summary(runtime_metrics, task_approval, audit, pilot_reports),
        "runtime_metrics_summary": {
            "total_task_count": runtime_metrics.get("total_task_count", 0),
            "total_tool_call_count": runtime_metrics.get("total_tool_call_count", 0),
            "total_prompt_tokens": runtime_metrics.get("total_prompt_tokens", 0),
            "total_completion_tokens": runtime_metrics.get("total_completion_tokens", 0),
            "total_tokens": runtime_metrics.get("total_tokens", 0),
            "total_cost": runtime_metrics.get("total_cost", 0.0),
        },
        "audit_recent_events": audit.get("recent_events", [])[:5],
        "pilot_reports_index": pilot_reports,
        "demo_evidence_paths": _collect_demo_evidence_paths(),
        "online_checks": online,
        "skipped": skipped,
        "limitations": [
            "default fake/offline path",
            "no real external LLM execution in default flow",
            "not public production approval",
        ],
        "boundary_declarations": [
            "not public production approval",
            "not real LLM production acceptance",
            "no raw prompt / no secrets",
        ],
    }
    sanitized = _sanitize_snapshot_payload(payload)

    file_stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_acceptance_snapshot"
    json_path = output_root / f"{file_stem}.json"
    md_path = output_root / f"{file_stem}.md"
    json_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(sanitized), encoding="utf-8")

    return {
        "status": sanitized.get("status", "unknown"),
        "snapshot_id": snapshot_id,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "skipped_count": len(skipped),
        "offline_only": bool(online.get("status") == "skipped"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成脱敏 acceptance snapshot（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-url", default="http://localhost:8000")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_acceptance_snapshot(output_dir=args.output_dir, base_url=args.base_url)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("offline_only"):
        print("status=completed_with_skipped_online_checks")
    else:
        print("status=completed")
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
