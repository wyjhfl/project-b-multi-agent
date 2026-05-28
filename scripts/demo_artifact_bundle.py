from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.operations import _collect_pilot_report_summary
from app.core.structured_logging import redact_sensitive_value
from app.harness.llm.pilot_report import REDACTED_PROMPT_PLACEHOLDER, sanitize_pilot_report_payload
from scripts.acceptance_snapshot import build_acceptance_snapshot

DEFAULT_ARTIFACT_DIR = ROOT_DIR / "docs" / "reports" / "demo_artifacts"

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

BOUNDARY_DECLARATIONS = [
    "not public production approval",
    "not real LLM production acceptance",
    "no raw prompt / no secrets",
]


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _write_json(path: Path, payload: Any) -> Path:
    sanitized = _sanitize_payload(payload)
    path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be dict: {path}")
    return payload

def _load_report_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return sanitize_pilot_report_payload(payload)


def _collect_pilot_report_summary_from_dir(report_dir: Path) -> dict[str, Any]:
    if not report_dir.exists() or not report_dir.is_dir():
        return {
            "report_dir": str(report_dir),
            "directory_exists": False,
            "total_reports": 0,
            "reports": [],
        }

    reports: list[dict[str, Any]] = []
    for path in sorted(report_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue

        payload = _load_report_json(path)
        if not payload:
            continue

        evidence_links = payload.get("evidence_links") or {}
        if not evidence_links and payload.get("cases"):
            first_case = payload["cases"][0] if isinstance(payload["cases"], list) and payload["cases"] else {}
            if isinstance(first_case, dict):
                evidence_links = first_case.get("evidence_links") or {}

        reports.append(
            {
                "report_id": payload.get("report_id") or path.stem,
                "generated_at": payload.get("generated_at", ""),
                "scenario": payload.get("scenario", ""),
                "outcome": payload.get("outcome", ""),
                "request_id": payload.get("request_id", ""),
                "fallback_used": bool(payload.get("fallback_used", False)),
                "cost": float(payload.get("cost", 0.0) or 0.0),
                "total_tokens": int(payload.get("total_tokens", 0) or 0),
                "audit_event_id": str(evidence_links.get("audit_event_id") or ""),
                "name": path.name,
            }
        )
        if len(reports) >= 10:
            break

    return {
        "report_dir": str(report_dir),
        "directory_exists": True,
        "total_reports": len(reports),
        "reports": reports,
    }


def _build_run_dir(output_dir: str | Path | None, run_dir: str | Path | None = None) -> tuple[Path, str, str]:
    generated_at = _utc_now_iso()
    short_commit = (_run_git(["rev-parse", "--short", "HEAD"]) or "unknown")[:8]

    if run_dir:
        run_dir_path = Path(run_dir)
        run_dir_path.mkdir(parents=True, exist_ok=True)
        return run_dir_path, generated_at, short_commit

    root = Path(output_dir) if output_dir else DEFAULT_ARTIFACT_DIR
    root.mkdir(parents=True, exist_ok=True)
    run_dir_path = root / f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}"
    run_dir_path.mkdir(parents=True, exist_ok=True)
    return run_dir_path, generated_at, short_commit


def _extract_operations_status(online_smoke_result: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    checks = online_smoke_result.get("checks") if isinstance(online_smoke_result, dict) else {}
    if not isinstance(checks, dict):
        return {"status": "skipped", "reason": "checks_unavailable", "path": ""}

    op_item = checks.get("operations_summary")
    if not isinstance(op_item, dict):
        return {"status": "skipped", "reason": "operations_summary_not_checked", "path": ""}

    op_status = str(op_item.get("status") or "unknown")
    if op_status == "ok" and isinstance(op_item.get("body"), dict):
        op_path = run_dir / "operations_summary.json"
        _write_json(op_path, op_item["body"])
        return {"status": "ok", "path": str(op_path), "reason": ""}

    return {
        "status": "skipped" if op_status == "skipped" else "failed",
        "reason": str(op_item.get("error") or "operations_summary_unavailable"),
        "path": "",
    }


def build_demo_artifact_bundle(
    *,
    artifact_dir: str | Path | None,
    base_url: str,
    seed_summary: dict[str, Any] | None,
    online_smoke_result: dict[str, Any],
    artifact_run_dir: str | Path | None = None,
    pilot_report_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_dir, generated_at, _short_commit = _build_run_dir(artifact_dir, artifact_run_dir)
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"

    seed_payload = seed_summary or {"status": "skipped", "reason": "skip_seed_switch"}
    seed_path = _write_json(run_dir / "seed_summary.json", seed_payload)
    online_path = _write_json(run_dir / "online_smoke_result.json", online_smoke_result)

    acceptance_dir = run_dir / "acceptance_snapshot"
    acceptance = build_acceptance_snapshot(output_dir=acceptance_dir, base_url=base_url)

    operations_summary = _extract_operations_status(online_smoke_result, run_dir)

    resolved_report_dir: Path | None = None
    if pilot_report_dir:
        resolved_report_dir = Path(pilot_report_dir)
    elif isinstance(seed_payload, dict):
        seed_report_dir = str(seed_payload.get("pilot_report_dir") or "").strip()
        if seed_report_dir:
            resolved_report_dir = Path(seed_report_dir)

    if resolved_report_dir is not None:
        pilot_index_payload = _collect_pilot_report_summary_from_dir(resolved_report_dir)
    else:
        pilot_index_payload = _collect_pilot_report_summary()

    pilot_index_path = _write_json(run_dir / "pilot_report_index.json", pilot_index_payload)

    online_status = str(online_smoke_result.get("status") or "unknown")
    bundle_status = "completed"
    if online_status == "skipped":
        bundle_status = "completed_with_skipped_online_checks"
    elif online_status in {"failed", "partial"}:
        bundle_status = "completed_with_partial_online_checks"

    summary = {
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "real_llm_executed": False,
        "status": bundle_status,
        "seed": {
            "status": str(seed_payload.get("status") or "unknown"),
            "path": str(seed_path),
            "skip_seed": bool(str(seed_payload.get("status", "")).lower() == "skipped"),
        },
        "online_smoke": {
            "status": online_status,
            "path": str(online_path),
            "skipped_reason": str(online_smoke_result.get("reason") or ""),
        },
        "operations_summary": operations_summary,
        "acceptance_snapshot": {
            "status": acceptance.get("status", "unknown"),
            "json_path": str(acceptance.get("json_path", "")),
            "markdown_path": str(acceptance.get("markdown_path", "")),
            "offline_only": bool(acceptance.get("offline_only", False)),
        },
        "pilot_report_index": {
            "status": "ok",
            "path": str(pilot_index_path),
            "report_dir": str(pilot_index_payload.get("report_dir", "")),
            "total_reports": int(pilot_index_payload.get("total_reports", 0) or 0),
        },
        "artifact_run_dir": str(run_dir),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    summary_path = _write_json(run_dir / "demo_e2e_summary.json", summary)
    return {
        "status": bundle_status,
        "artifact_run_dir": str(run_dir),
        "summary_path": str(summary_path),
        "seed_summary_path": str(seed_path),
        "online_smoke_result_path": str(online_path),
        "acceptance_snapshot_json_path": str(acceptance.get("json_path", "")),
        "acceptance_snapshot_markdown_path": str(acceptance.get("markdown_path", "")),
        "pilot_report_index_path": str(pilot_index_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build demo artifact bundle for offline acceptance evidence")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--seed-input", required=False)
    parser.add_argument("--online-input", required=True)
    parser.add_argument("--artifact-run-dir", required=False)
    parser.add_argument("--pilot-report-dir", required=False)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    online_payload = _read_json(Path(args.online_input))
    seed_payload = _read_json(Path(args.seed_input)) if args.seed_input else None

    summary = build_demo_artifact_bundle(
        artifact_dir=args.artifact_dir,
        base_url=args.base_url,
        seed_summary=seed_payload,
        online_smoke_result=online_payload,
        artifact_run_dir=args.artifact_run_dir,
        pilot_report_dir=args.pilot_report_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"bundle_summary_path={summary['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
