from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.operations import _collect_pilot_report_summary
from app.auth.oidc_config import validate_oidc_settings
from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.core.structured_logging import redact_sensitive_value
from app.harness.llm.pilot_report import REDACTED_PROMPT_PLACEHOLDER, sanitize_pilot_report_payload

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "failure_diagnostics"
DEFAULT_BASE_URL = "http://localhost:8000"

PROD_REQUIRED_ENV_VARS = ("JWT_SECRET", "DATABASE_URL", "REDIS_URL")
REAL_LLM_REQUIRED_VARS = (
    "REAL_LLM_SMOKE_ENABLED",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_PREFLIGHT_ENABLED",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    "REAL_LLM_MODEL",
    "REAL_LLM_API_KEY_ENV",
)
PLACEHOLDER_MARKERS = (
    "changeme",
    "change_me",
    "placeholder",
    "replace",
    "example",
    "demo",
    "your_",
    "dummy",
    "fake",
    "test",
)

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _is_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _sanitize_key_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if key_lower in _EVIDENCE_SAFE_KEYS:
        return _sanitize_payload(value)
    if any(marker in key_lower for marker in _PROMPT_KEY_MARKERS):
        return REDACTED_PROMPT_PLACEHOLDER
    if any(marker in key_lower for marker in _SENSITIVE_KEY_MARKERS) and key_lower not in _SAFE_TOKEN_KEYS:
        return redact_sensitive_value(value)
    return _sanitize_payload(value)


def _sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _sanitize_key_value(str(key), value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_sanitize_payload(item) for item in payload]
    return sanitize_pilot_report_payload(payload)


def _run_command(command: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd or ROOT_DIR),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=20,
            check=False,
        )
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "return_code": proc.returncode,
            "command": " ".join(command),
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {
            "status": "skipped",
            "return_code": -1,
            "command": " ".join(command),
            "stdout": "",
            "stderr": str(exc),
        }


def _read_json_url(url: str, timeout: float = 5.0) -> tuple[int, dict[str, Any] | None, str]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": body[:2000]}
            if not isinstance(payload, dict):
                payload = {"value": payload}
            return int(resp.status), payload, ""
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        payload: dict[str, Any] | None = None
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                payload = loaded
            else:
                payload = {"value": loaded}
        except Exception:
            payload = {"raw": text[:2000]}
        return int(exc.code), payload, ""
    except URLError as exc:
        return 0, None, str(exc)
    except Exception as exc:
        return 0, None, str(exc)


def _collect_online_summary(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    health_status, health_payload, health_error = _read_json_url(f"{base}/health")
    if health_status == 0:
        return {
            "status": "skipped",
            "reason": "service_unavailable",
            "checks": {
                "health": {"status": "skipped", "error": health_error},
                "deployment_check": {"status": "skipped", "reason": "health_unavailable"},
                "operations_summary": {"status": "skipped", "reason": "health_unavailable"},
                "audit_export": {"status": "skipped", "reason": "health_unavailable"},
            },
        }

    checks: dict[str, Any] = {
        "health": {"status": "ok" if health_status == 200 else "failed", "http_status": health_status, "data": health_payload}
    }

    dep_status, dep_payload, dep_error = _read_json_url(f"{base}/deployment/check")
    checks["deployment_check"] = {
        "status": "ok" if dep_status == 200 else "failed",
        "http_status": dep_status,
        "data": dep_payload,
        "error": dep_error,
    }

    ops_status, ops_payload, ops_error = _read_json_url(f"{base}/operations/summary")
    checks["operations_summary"] = {
        "status": "ok" if ops_status == 200 else "failed",
        "http_status": ops_status,
        "data": ops_payload,
        "error": ops_error,
    }

    audit_status, audit_payload, audit_error = _read_json_url(f"{base}/audit/events/export?limit=1")
    checks["audit_export"] = {
        "status": "ok" if audit_status == 200 else "failed",
        "http_status": audit_status,
        "data": audit_payload,
        "error": audit_error,
    }

    overall = "ok"
    if any(item.get("status") == "failed" for item in checks.values()):
        overall = "partial"
    return {"status": overall, "reason": "", "checks": checks}


def _find_latest_json(pattern: str) -> Path | None:
    matches = sorted(ROOT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _safe_load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _diagnose_prod_required_env() -> dict[str, Any]:
    missing: list[str] = []
    placeholder: list[str] = []
    for key in PROD_REQUIRED_ENV_VARS:
        value = (os.getenv(key, "") or "").strip()
        if not value:
            missing.append(key)
            continue
        if _is_placeholder(value):
            placeholder.append(key)

    status = "ok"
    if missing:
        status = "blocked"
    elif placeholder:
        status = "warning"

    return {
        "status": status,
        "missing_required_env": missing,
        "placeholder_env": placeholder,
    }


def _diagnose_real_llm_opt_in() -> dict[str, Any]:
    missing: list[str] = []
    placeholder: list[str] = []
    for key in REAL_LLM_REQUIRED_VARS:
        value = (os.getenv(key, "") or "").strip()
        if not value:
            missing.append(key)
        elif _is_placeholder(value):
            placeholder.append(key)

    api_key_env_name = (os.getenv("REAL_LLM_API_KEY_ENV", "") or "").strip()
    if api_key_env_name:
        real_key = (os.getenv(api_key_env_name, "") or "").strip()
        if not real_key:
            missing.append(api_key_env_name)
        elif _is_placeholder(real_key):
            placeholder.append(api_key_env_name)

    status = "skipped" if missing else ("warning" if placeholder else "ready")
    return {
        "status": status,
        "missing_env": sorted(set(missing)),
        "placeholder_env": sorted(set(placeholder)),
        "real_llm_executed": False,
    }


def _diagnose_oidc_secret_env() -> dict[str, Any]:
    validation = validate_oidc_settings(settings)
    secret_errors = [item for item in validation.get("errors", []) if "未注入或为空" in str(item)]
    if not bool(settings.oidc_enabled):
        return {"status": "skipped", "reason": "oidc_disabled"}
    if secret_errors:
        return {"status": "blocked", "errors": secret_errors}
    return {"status": "ok", "errors": []}


def _diagnose_demo_online_skipped() -> dict[str, Any]:
    latest = _find_latest_json("docs/reports/demo_artifacts/*/online_smoke_result.json")
    payload = _safe_load_json(latest)
    if not latest or not payload:
        return {"status": "skipped", "reason": "no_artifact_found"}
    status = str(payload.get("status") or "unknown")
    if status == "skipped":
        return {"status": "blocked", "reason": str(payload.get("reason") or "unknown"), "path": str(latest)}
    return {"status": "ok", "observed_status": status, "path": str(latest)}


def _diagnose_acceptance_online_skipped() -> dict[str, Any]:
    latest = _find_latest_json("docs/reports/acceptance_snapshots/*_acceptance_snapshot.json")
    payload = _safe_load_json(latest)
    if not latest or not payload:
        return {"status": "skipped", "reason": "no_snapshot_found"}
    online_checks = payload.get("online_checks") if isinstance(payload.get("online_checks"), dict) else {}
    online_status = str(online_checks.get("status") or "")
    if online_status == "skipped":
        return {"status": "blocked", "reason": str(online_checks.get("reason") or "service_unavailable"), "path": str(latest)}
    return {"status": "ok", "observed_status": online_status or "unknown", "path": str(latest)}


def _build_markdown(report: dict[str, Any]) -> str:
    scenarios = report.get("scenarios", {})
    lines = [
        "# Failure Diagnostics Pack v3.2",
        "",
        f"- generated_at: {report.get('generated_at', '')}",
        f"- commit: {report.get('commit', '')}",
        f"- version: {report.get('version', '')}",
        f"- mode: {report.get('mode', '')}",
        "",
        "## Scenario Status",
    ]

    for key, value in scenarios.items():
        if isinstance(value, dict):
            lines.append(f"- {key}: {value.get('status', 'unknown')}")
        else:
            lines.append(f"- {key}: unknown")

    lines.extend(
        [
            "",
            "## Boundary Declarations",
            "- read only diagnostics: no write/delete operation",
            "- no real external LLM execution",
            "- fake/offline default preserved",
            "- no raw prompt / no secrets",
            "- not public production approval",
            "",
        ]
    )
    return "\n".join(lines)


def build_failure_diagnostics(
    *,
    output_dir: str | Path | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_compose_checks: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    report_id = f"failure-diagnostics-{generated_at.replace(':', '-').replace('+', '_')}-{short_commit}"

    online = _collect_online_summary(base_url)
    deployment_offline = run_deployment_checks().model_dump()
    prod_env = _diagnose_prod_required_env()
    pilot_reports = _collect_pilot_report_summary()
    real_llm = _diagnose_real_llm_opt_in()
    oidc_secret = _diagnose_oidc_secret_env()
    demo_online = _diagnose_demo_online_skipped()
    acceptance_online = _diagnose_acceptance_online_skipped()

    compose_default = {"status": "skipped", "reason": "run_compose_checks_disabled"}
    compose_prod = {"status": "skipped", "reason": "run_compose_checks_disabled"}
    if run_compose_checks:
        compose_default = _run_command(["docker", "compose", "config"])
        compose_prod = _run_command(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml", "config"])

    deployment_online = online.get("checks", {}).get("deployment_check", {})
    deployment_online_ok = None
    if isinstance(deployment_online, dict):
        dep_data = deployment_online.get("data")
        if isinstance(dep_data, dict) and "ok" in dep_data:
            deployment_online_ok = bool(dep_data.get("ok"))

    deployment_scenario_status = "ok"
    deployment_detail: dict[str, Any] = {
        "offline_ok": bool(deployment_offline.get("ok", False)),
        "offline_errors": deployment_offline.get("errors", []),
    }
    if deployment_online_ok is False:
        deployment_scenario_status = "blocked"
        deployment_detail["online_ok"] = False
    elif deployment_online_ok is True:
        deployment_detail["online_ok"] = True
    elif online.get("status") == "skipped":
        deployment_scenario_status = "skipped"
        deployment_detail["reason"] = "service_unavailable"

    operations_online = online.get("checks", {}).get("operations_summary", {})
    operations_status = "ok"
    if online.get("status") == "skipped":
        operations_status = "skipped"
    elif isinstance(operations_online, dict) and operations_online.get("status") == "failed":
        operations_status = "blocked"

    audit_online = online.get("checks", {}).get("audit_export", {})
    audit_status = "skipped" if online.get("status") == "skipped" else "ok"
    audit_reason = ""
    if isinstance(audit_online, dict):
        if int(audit_online.get("http_status", 0) or 0) == 403:
            payload = audit_online.get("data") if isinstance(audit_online.get("data"), dict) else {}
            if str(payload.get("error") or "") == "audit_export_redaction_required":
                audit_status = "blocked"
                audit_reason = "audit_export_redaction_required"
        elif audit_online.get("status") == "failed":
            audit_status = "blocked"
            audit_reason = str(audit_online.get("error") or "audit_export_failed")

    scenarios = {
        "docker_compose_config": {
            "status": compose_default.get("status", "unknown"),
            "return_code": compose_default.get("return_code", -1),
            "stderr": compose_default.get("stderr", ""),
        },
        "prod_compose_missing_required_env": {
            "status": prod_env.get("status", "unknown"),
            "missing_required_env": prod_env.get("missing_required_env", []),
            "placeholder_env": prod_env.get("placeholder_env", []),
            "compose_config_status": compose_prod.get("status", "unknown"),
            "compose_return_code": compose_prod.get("return_code", -1),
            "compose_stderr": compose_prod.get("stderr", ""),
        },
        "deployment_check_ok_false": {
            "status": deployment_scenario_status,
            "detail": deployment_detail,
        },
        "operations_service_unavailable": {
            "status": operations_status,
            "detail": operations_online if isinstance(operations_online, dict) else {},
        },
        "demo_e2e_online_smoke_skipped": demo_online,
        "acceptance_snapshot_online_checks_skipped": acceptance_online,
        "pilot_reports_empty": {
            "status": "blocked" if int(pilot_reports.get("total_reports", 0) or 0) == 0 else "ok",
            "report_dir": pilot_reports.get("report_dir", ""),
            "total_reports": int(pilot_reports.get("total_reports", 0) or 0),
            "directory_exists": bool(pilot_reports.get("directory_exists", False)),
        },
        "audit_export_redaction_required_403": {
            "status": audit_status,
            "reason": audit_reason,
            "http_status": int(audit_online.get("http_status", 0) or 0) if isinstance(audit_online, dict) else 0,
        },
        "oidc_client_secret_env_missing": oidc_secret,
        "real_llm_opt_in_skipped": real_llm,
    }

    payload = {
        "report_id": report_id,
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.2.0",
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "service_base_url": base_url.rstrip("/"),
        "online_checks": online,
        "scenarios": scenarios,
        "boundary_declarations": [
            "read only diagnostics: no write/delete operation",
            "no real external LLM execution",
            "fake/offline default preserved",
            "no raw prompt / no secrets",
            "not public production approval",
            "not real LLM production acceptance",
        ],
        "limitations": [
            "service unavailable will mark online checks as skipped",
            "compose checks may be skipped if docker CLI is unavailable",
            "does not modify environment variables",
        ],
    }

    sanitized = _sanitize_payload(payload)
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_failure_diagnostics"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(sanitized), encoding="utf-8")

    return {
        "status": "ok",
        "report_id": report_id,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate read-only failure diagnostics pack (JSON + Markdown)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--skip-compose-checks",
        action="store_true",
        help="Skip docker compose commands in diagnostics output",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_failure_diagnostics(
        output_dir=args.output_dir,
        base_url=args.base_url,
        run_compose_checks=not bool(args.skip_compose_checks),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
