from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "live_drill_window"
DEFAULT_BASE_URL = os.getenv("LIVE_DRILL_BASE_URL", "http://127.0.0.1:8000")

SERVICE_ENDPOINTS = {
    "health": "/health",
    "deployment_check": "/deployment/check",
    "operations_summary": "/operations/summary",
}

REQUIRED_REAL_LLM_ENV = [
    "REAL_LLM_SMOKE_ENABLED",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_PREFLIGHT_ENABLED",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    "REAL_LLM_MODEL",
    "REAL_LLM_API_KEY_ENV",
]

OIDC_REQUIRED_ENV = [
    "OIDC_ENABLED",
    "OIDC_ISSUER_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET_ENV",
    "OIDC_REDIRECT_URI",
]

AUTOMATION_SCRIPTS = [
    "scripts/acceptance_snapshot.py",
    "scripts/demo_artifact_bundle.py",
    "scripts/failure_diagnostics.py",
    "scripts/config_drift_check.py",
    "scripts/governance_policy_summary.py",
]

BOUNDARY_DECLARATIONS = [
    "default fake/offline",
    "default pytest/CI does not call real LLM",
    "read-only precheck only",
    "no user data deletion",
    "no automatic report cleanup",
    "no .env mutation",
    "no real secret plaintext output",
    "no public production direct launch approval",
    "not real LLM production acceptance completion",
    "not production-grade SSO/OIDC completion",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        out = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return out.strip()
    except Exception:
        return ""


def _to_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return str(path)


def _http_check(url: str) -> dict[str, Any]:
    req = request.Request(url=url, method="GET")
    try:
        with request.urlopen(req, timeout=2.5) as resp:
            return {"reachable": True, "http_status": int(resp.status)}
    except error.HTTPError as exc:
        return {"reachable": True, "http_status": int(exc.code)}
    except Exception as exc:
        return {"reachable": False, "error": type(exc).__name__}


def _is_true_text(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_service_window(base_url: str) -> tuple[dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    missing: list[str] = []
    for key, path in SERVICE_ENDPOINTS.items():
        result = _http_check(base_url.rstrip("/") + path)
        checks[key] = result
        if not result.get("reachable", False):
            missing.append(f"service_unavailable:{key}")
    return checks, missing


def _build_script_readiness() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in AUTOMATION_SCRIPTS:
        p = ROOT_DIR / rel
        exists = p.exists()
        rows.append({"script": rel, "exists": exists})
        if not exists:
            missing.append(f"script_missing:{rel}")
    return rows, missing


def _build_real_llm_opt_in() -> tuple[dict[str, Any], list[str]]:
    missing: list[str] = []
    details: dict[str, Any] = {}

    for key in REQUIRED_REAL_LLM_ENV:
        value = os.getenv(key)
        present = bool(value)
        details[key] = {"present": present}
        if not present:
            missing.append(key)

    api_key_env_name = os.getenv("REAL_LLM_API_KEY_ENV", "").strip()
    api_key_target_present = bool(api_key_env_name and os.getenv(api_key_env_name))
    details["REAL_LLM_API_KEY_ENV_TARGET"] = {
        "env_name": api_key_env_name if api_key_env_name else "",
        "present": api_key_target_present,
    }
    if not api_key_target_present:
        missing.append("REAL_LLM_API_KEY_ENV_TARGET")

    flags_true = {
        "REAL_LLM_SMOKE_ENABLED": _is_true_text(os.getenv("REAL_LLM_SMOKE_ENABLED")),
        "REAL_LLM_ACCEPTANCE_ENABLED": _is_true_text(os.getenv("REAL_LLM_ACCEPTANCE_ENABLED")),
        "REAL_LLM_PREFLIGHT_ENABLED": _is_true_text(os.getenv("REAL_LLM_PREFLIGHT_ENABLED")),
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK": _is_true_text(os.getenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK")),
    }
    details["flags_true"] = flags_true

    live_execution_switch = all(flags_true.values())
    details["explicit_live_switch"] = live_execution_switch
    details["eligible_for_real_llm"] = live_execution_switch and not missing
    details["real_llm_executed"] = False

    return details, missing


def _build_oidc_readiness() -> tuple[dict[str, Any], list[str]]:
    missing: list[str] = []
    rows: dict[str, Any] = {}
    for key in OIDC_REQUIRED_ENV:
        value = os.getenv(key)
        present = bool(value)
        rows[key] = {"present": present}
        if not present:
            missing.append(key)

    secret_env_name = os.getenv("OIDC_CLIENT_SECRET_ENV", "").strip()
    secret_target_present = bool(secret_env_name and os.getenv(secret_env_name))
    rows["OIDC_CLIENT_SECRET_ENV_TARGET"] = {
        "env_name": secret_env_name if secret_env_name else "",
        "present": secret_target_present,
    }
    if not secret_target_present:
        missing.append("OIDC_CLIENT_SECRET_ENV_TARGET")

    rows["oidc_enabled_true"] = _is_true_text(os.getenv("OIDC_ENABLED"))
    return rows, missing


def _derive_status(*, service_missing: list[str], script_missing: list[str], llm_missing: list[str], oidc_missing: list[str]) -> str:
    if script_missing:
        return "blocked"
    if llm_missing or oidc_missing:
        return "skipped"
    if service_missing:
        return "partial"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Optional Live Drill Window Summary (Read Only)",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- mode: {payload.get('mode', '')}",
        "",
        "## Missing Conditions",
    ]
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Boundary Declarations",
    ])
    for b in payload.get("boundary_declarations", []):
        lines.append(f"- {b}")
    lines.append("")
    return "\n".join(lines)


def build_live_drill_window_summary(*, output_dir: str | Path | None = None, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    service_checks, service_missing = _build_service_window(base_url)
    scripts_readiness, script_missing = _build_script_readiness()
    llm_opt_in, llm_missing = _build_real_llm_opt_in()
    oidc_readiness, oidc_missing = _build_oidc_readiness()

    missing_conditions = service_missing + script_missing + llm_missing + oidc_missing
    status = _derive_status(
        service_missing=service_missing,
        script_missing=script_missing,
        llm_missing=llm_missing,
        oidc_missing=oidc_missing,
    )

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.4.0",
        "mode": "fake_offline_default",
        "status": status,
        "service_window": service_checks,
        "acceptance_snapshot_ready": any(r["script"] == "scripts/acceptance_snapshot.py" and r["exists"] for r in scripts_readiness),
        "demo_artifact_bundle_ready": any(r["script"] == "scripts/demo_artifact_bundle.py" and r["exists"] for r in scripts_readiness),
        "failure_diagnostics_ready": any(r["script"] == "scripts/failure_diagnostics.py" and r["exists"] for r in scripts_readiness),
        "config_drift_ready": any(r["script"] == "scripts/config_drift_check.py" and r["exists"] for r in scripts_readiness),
        "governance_summary_ready": any(r["script"] == "scripts/governance_policy_summary.py" and r["exists"] for r in scripts_readiness),
        "script_readiness": scripts_readiness,
        "real_llm_opt_in": llm_opt_in,
        "oidc_live_drill": oidc_readiness,
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "real_llm_executed": False,
        "read_only": True,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_live_drill_window"
    json_path = out_root / f"{stem}.json"
    md_path = out_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(out_root),
        "missing_count": len(missing_conditions),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build optional live drill window summary (read-only JSON + Markdown)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_live_drill_window_summary(output_dir=args.output_dir, base_url=args.base_url)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
