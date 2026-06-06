from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_evidence_freshness"

DEFAULT_SOURCES = {
    "production_landing_status": (
        ROOT_DIR / "docs" / "reports" / "production_landing_status",
        "*_production_landing_status.json",
    ),
    "production_landing_final_verification": (
        ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
        "*_production_landing_final_verification.json",
    ),
    "controlled_pilot_status_summary": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_status_summary",
        "*_controlled_pilot_status_summary.json",
    ),
    "controlled_pilot_operator_packet": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_operator_packet",
        "*_controlled_pilot_operator_packet.json",
    ),
    "business_system_input_packet": (
        ROOT_DIR / "docs" / "reports" / "business_system_input_packet",
        "*_business_system_input_packet.json",
    ),
    "business_system_production_readiness": (
        ROOT_DIR / "docs" / "reports" / "business_system_production_readiness",
        "*_business_system_production_readiness.json",
    ),
    "business_system_landing_execution_pack": (
        ROOT_DIR / "docs" / "reports" / "business_system_landing_execution_pack",
        "*_business_system_landing_execution_pack.json",
    ),
    "production_landing_text_quality": (
        ROOT_DIR / "docs" / "reports" / "production_landing_text_quality",
        "*_production_landing_text_quality.json",
    ),
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "<secret-managed-token>",
    "<secret-managed-url>",
    "<set-in-local-env-only>",
    "<owner-or-staff-id>",
    "secret-managed-token",
    "secret-managed-url",
    "set-in-local-env-only",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _worktree_clean() -> bool:
    return _run_git(["status", "--porcelain"]) == ""


def _contains_secret_like(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like(key) or _contains_secret_like(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like(item) for item in value)
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>):").lower()
                if not candidate or candidate in SAFE_SECRET_PLACEHOLDERS:
                    continue
                if candidate.startswith("真实"):
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {_redact(str(key)): _redact(item) for key, item in value.items()}
    return value


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return generated_at, item.stat().st_mtime, item.name

    return max(files, key=sort_key)


def _commit_matches(report_commit: str, current_commit: str) -> bool:
    report_commit = report_commit.strip()
    current_commit = current_commit.strip()
    if not report_commit or not current_commit or current_commit == "unknown":
        return False
    if report_commit == current_commit:
        return True
    if len(report_commit) >= 8 and current_commit.startswith(report_commit):
        return True
    if len(current_commit) >= 8 and report_commit.startswith(current_commit):
        return True
    return False


def _read_source(source_id: str, directory: Path, pattern: str, current_commit: str) -> dict[str, Any]:
    path = _latest_json(directory, pattern)
    if path is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "missing",
            "latest_json_path": "",
            "generated_at": "",
            "report_commit": "",
            "commit_matches_head": False,
            "secret_like_detected": False,
            "missing_conditions": [f"{source_id}:report_not_found"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "source_id": source_id,
            "present": True,
            "status": "blocked",
            "latest_json_path": str(path),
            "generated_at": "",
            "report_commit": "",
            "commit_matches_head": False,
            "secret_like_detected": False,
            "missing_conditions": [f"{source_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        return {
            "source_id": source_id,
            "present": True,
            "status": "blocked",
            "latest_json_path": str(path),
            "generated_at": "",
            "report_commit": "",
            "commit_matches_head": False,
            "secret_like_detected": False,
            "missing_conditions": [f"{source_id}:json_object_required"],
        }

    report_commit = str(payload.get("commit") or "")
    secret_like_detected = _contains_secret_like(payload)
    commit_matches = _commit_matches(report_commit, current_commit)
    missing = []
    if not report_commit:
        missing.append(f"{source_id}:commit_missing")
    if not commit_matches:
        missing.append(f"{source_id}:commit_not_current_head")
    if secret_like_detected or payload.get("secret_plaintext_output") is True:
        missing.append(f"{source_id}:secret_like_output_detected")

    return {
        "source_id": source_id,
        "present": True,
        "status": str(payload.get("status") or "unknown"),
        "latest_json_path": str(path),
        "generated_at": str(payload.get("generated_at") or ""),
        "report_commit": report_commit,
        "commit_matches_head": commit_matches,
        "secret_like_detected": secret_like_detected,
        "secret_plaintext_output": payload.get("secret_plaintext_output"),
        "missing_conditions": missing,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地证据新鲜度检查",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- current_commit: {payload.get('current_commit', '')}",
        f"- worktree_clean: {payload.get('worktree_clean', False)}",
        f"- stale_source_count: {payload.get('stale_source_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Sources",
    ]
    for item in payload.get("sources", []):
        lines.append(
            f"- {item.get('source_id')}: present={item.get('present')} "
            f"commit_matches_head={item.get('commit_matches_head')} missing={item.get('missing_conditions', [])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_production_landing_evidence_freshness(
    *,
    output_dir: str | Path | None = None,
    sources: dict[str, tuple[str | Path, str]] | None = None,
    current_commit: str | None = None,
    worktree_clean: bool | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    head_commit = current_commit or _run_git(["rev-parse", "HEAD"]) or "unknown"
    clean = _worktree_clean() if worktree_clean is None else bool(worktree_clean)
    source_map = sources or DEFAULT_SOURCES
    source_results = [
        _read_source(source_id, Path(directory), pattern, head_commit)
        for source_id, (directory, pattern) in source_map.items()
    ]
    missing_conditions: list[str] = []
    for item in source_results:
        missing_conditions.extend(str(condition) for condition in item.get("missing_conditions", []))
    if not clean:
        missing_conditions.append("git:worktree_dirty")

    secret_like_output = any(item.get("secret_like_detected") for item in source_results)
    stale_count = sum(
        1
        for item in source_results
        if not item.get("present") or item.get("commit_matches_head") is not True
    )
    status = "blocked" if secret_like_output else ("success" if not missing_conditions else "partial")
    payload = {
        "generated_at": generated_at,
        "commit": head_commit,
        "version": "4.8.22",
        "phase": "v4.8 Production Landing Evidence Freshness",
        "status": status,
        "mode": "read_only_evidence_freshness",
        "read_only": True,
        "current_commit": head_commit,
        "worktree_clean": clean,
        "source_count": len(source_results),
        "stale_source_count": stale_count,
        "sources": [_redact(item) for item in source_results],
        "missing_conditions": sorted(set(_redact(missing_conditions))),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = head_commit[:8] if head_commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_evidence_freshness"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "source_count": payload["source_count"],
        "stale_source_count": payload["stale_source_count"],
        "worktree_clean": payload["worktree_clean"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地证据新鲜度检查报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_evidence_freshness(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
