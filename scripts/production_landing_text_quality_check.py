from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_text_quality"

DEFAULT_TARGETS = [
    ROOT_DIR / "pyproject.toml",
    ROOT_DIR / "docs" / "codex_windows_environment_guard_v48.md",
    ROOT_DIR / "docs" / "business_system_read_smoke_v45.md",
    ROOT_DIR / "docs" / "production_landing_signoff_closeout_runbook_v48.md",
    ROOT_DIR / "docs" / "production_landing_operator_runbook_v47.md",
    ROOT_DIR / "docs" / "xiaomi_llm_landing_resume_runbook_v47.md",
    ROOT_DIR / "docs" / "manual_signoff_package_v41.md",
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.template.json",
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.draft.json",
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.json",
    ROOT_DIR / "scripts" / "production_landing_action_pack.py",
    ROOT_DIR / "scripts" / "manual_signoff_package.py",
    ROOT_DIR / "scripts" / "manual_signoff_record_validator.py",
    ROOT_DIR / "scripts" / "manual_signoff_record_promote.py",
    ROOT_DIR / "scripts" / "production_landing_pre_signoff_gate.py",
    ROOT_DIR / "scripts" / "production_landing_signoff_reviewer_packet.py",
    ROOT_DIR / "scripts" / "production_landing_signoff_closeout.py",
    ROOT_DIR / "scripts" / "production_landing_signoff_closeout.ps1",
    ROOT_DIR / "scripts" / "business_system_read_smoke.py",
    ROOT_DIR / "scripts" / "business_system_production_readiness_brief.py",
    ROOT_DIR / "scripts" / "business_system_input_packet.py",
    ROOT_DIR / "scripts" / "business_system_read_smoke.ps1",
    ROOT_DIR / "scripts" / "production_landing_evidence_freshness.py",
    ROOT_DIR / "scripts" / "xiaomi_llm_landing_resume.ps1",
]
OPTIONAL_TARGETS = {
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.template.json",
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.draft.json",
    ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.json",
}

MOJIBAKE_MARKERS = (
    "鐢熶骇",
    "鐪熷疄",
    "鍙",
    "杩愯惀",
    "涓彴",
    "娴嬭瘯",
    "锛",
    "燂",
    "纭",
    "鍙",
    "閻",
    "閸",
    "鐢熴",
    "鐢熵骇",
    "钀藉湴",
    "鎵",
    "绛",
    "涓嶈",
    "灏忕背",
    "浜哄伐",
    "瀵嗛挜",
    "杈圭晫",
)
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
    "真实只读",
    "真实业务系统",
}
SAFE_CODE_ASSIGNMENT_PREFIXES = (
    "$",
    "-",
    "[",
    "@{",
    "@(",
    "read-host",
    "convert-securestringtoplaintext",
    "new-object",
    "join-path",
)
SAFE_CODE_ASSIGNMENT_VALUES = {
    "0",
    "1",
    "true",
    "false",
    '""',
    "''",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(text: str) -> bool:
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>):").lower()
                if not candidate or candidate in SAFE_SECRET_PLACEHOLDERS:
                    continue
                if candidate.startswith("真实"):
                    continue
                if candidate in SAFE_CODE_ASSIGNMENT_VALUES:
                    continue
                if any(candidate.startswith(prefix) for prefix in SAFE_CODE_ASSIGNMENT_PREFIXES):
                    continue
            return True
    return False


def _scan_file(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "required": required,
            "status": "blocked" if required else "skipped",
            "mojibake_markers": [],
            "secret_like_detected": False,
            "missing_conditions": ["file:not_found"] if required else [],
        }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {
            "path": str(path),
            "exists": True,
            "required": required,
            "status": "blocked",
            "mojibake_markers": [],
            "secret_like_detected": False,
            "missing_conditions": ["file:utf8_read_failed"],
        }
    markers = sorted({marker for marker in MOJIBAKE_MARKERS if marker in text})
    secret_like = _contains_secret_like(text)
    missing = []
    if markers:
        missing.append("text:mojibake_marker_detected")
    if secret_like:
        missing.append("text:secret_like_detected")
    return {
        "path": str(path),
        "exists": True,
        "required": required,
        "status": "success" if not missing else "blocked",
        "mojibake_markers": markers,
        "secret_like_detected": secret_like,
        "missing_conditions": missing,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing text quality check",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- checked_file_count: {payload.get('checked_file_count', 0)}",
        f"- blocked_file_count: {payload.get('blocked_file_count', 0)}",
        "",
        "## Files",
    ]
    for item in payload.get("files", []):
        lines.append(
            f"- {item.get('status')}: {item.get('path')} "
            f"missing={','.join(item.get('missing_conditions', [])) or '-'}"
        )
    lines.append("")
    return "\n".join(lines)


def build_production_landing_text_quality_check(
    *,
    targets: list[str | Path] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    target_paths = [Path(item) for item in (targets or DEFAULT_TARGETS)]
    optional_targets = {path.resolve() for path in OPTIONAL_TARGETS} if targets is None else set()
    files = [_scan_file(path, required=path.resolve() not in optional_targets) for path in target_paths]
    blocked_count = sum(1 for item in files if item.get("status") == "blocked")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.7",
        "phase": "v4.7 Production Landing Text Quality Check",
        "status": "success" if blocked_count == 0 else "blocked",
        "mode": "read_only_text_quality_check",
        "read_only": True,
        "checked_file_count": len(files),
        "blocked_file_count": blocked_count,
        "files": files,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_text_quality"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "checked_file_count": len(files),
        "blocked_file_count": blocked_count,
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check production landing text artifacts for mojibake and secret-like text.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--target", action="append", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_text_quality_check(
        targets=args.target,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

