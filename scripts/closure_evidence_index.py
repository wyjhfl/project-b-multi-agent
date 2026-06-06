from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "closure_evidence_index"

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

BOUNDARY_DECLARATIONS = [
    "只读 closure evidence index",
    "仅扫描 closure workflow JSON 报告",
    "不读取 Markdown 报告正文",
    "不读取或输出真实 secret 原文",
    "不修改、不移动、不删除输入证据",
    "不自动关闭 blocker，不自动批准上线",
    "不执行真实外网 LLM，不连接真实外部系统",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、安全扫描、审计导出、密钥轮换或权限变更",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_payload(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _to_rel(path: Path) -> str:
    try:
        return _sanitize_text(path.resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return _sanitize_text(path)


def _format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _load_report(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"json_parse_failed:{_to_rel(path)}:{type(exc).__name__}"]
    if not isinstance(payload, dict) or not payload:
        return None, [f"json_empty_or_not_object:{_to_rel(path)}"]
    if _contains_secret_like_payload(payload):
        return None, [f"secret_like_value_detected:{_to_rel(path)}"]
    return payload, []


def _report_row(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    stat = path.stat()
    closure_items = payload.get("closure_items") if isinstance(payload.get("closure_items"), list) else []
    state_counts: dict[str, int] = {}
    for item in closure_items:
        if isinstance(item, dict):
            state = _sanitize_text(item.get("closure_state") or "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
    evidence_readiness_summary = (
        payload.get("evidence_readiness_summary")
        if isinstance(payload.get("evidence_readiness_summary"), dict)
        else {}
    )
    return {
        "path": _to_rel(path),
        "size_bytes": stat.st_size,
        "modified_at": _format_ts(stat.st_mtime),
        "generated_at": _sanitize_text(payload.get("generated_at") or ""),
        "status": _sanitize_text(payload.get("status") or "skipped"),
        "version": _sanitize_text(payload.get("version") or ""),
        "phase": _sanitize_text(payload.get("phase") or ""),
        "read_only": bool(payload.get("read_only", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
        "unexpected_execution_flags": [
            flag
            for flag in [
                "real_llm_executed",
                "external_mcp_connected",
                "external_system_connected",
                "deployment_executed",
                "migration_executed",
                "release_created",
                "tag_created",
                "rollback_executed",
                "security_scan_executed",
                "secret_rotation_executed",
                "audit_export_executed",
            ]
            if bool(payload.get(flag, False))
        ],
        "production_direct_launch": _sanitize_text(
            (payload.get("go_no_go") or {}).get("production_direct_launch", "")
            if isinstance(payload.get("go_no_go"), dict)
            else ""
        ),
        "closure_item_count": int(payload.get("closure_item_count") or len(closure_items)),
        "review_ready_count": int(payload.get("review_ready_count") or 0),
        "evidence_missing_count": int(payload.get("evidence_missing_count") or 0),
        "evidence_incomplete_count": int(payload.get("evidence_incomplete_count") or 0),
        "blocked_closure_count": int(payload.get("blocked_closure_count") or 0),
        "skipped_closure_count": int(payload.get("skipped_closure_count") or 0),
        "closure_state_counts": state_counts,
        "evidence_readiness_summary": {
            "local_evidence_available_count": int(
                evidence_readiness_summary.get("local_evidence_available_count", 0) or 0
            ),
            "runbook_only_count": int(evidence_readiness_summary.get("runbook_only_count", 0) or 0),
            "missing_count": int(evidence_readiness_summary.get("missing_count", 0) or 0),
            "manual_review_required": bool(evidence_readiness_summary.get("manual_review_required", False)),
            "auto_approved": bool(evidence_readiness_summary.get("auto_approved", False)),
            "auto_closed": bool(evidence_readiness_summary.get("auto_closed", False)),
        },
    }


def _derive_status(rows: list[dict[str, Any]], warnings: list[str]) -> str:
    if any("secret_like_value_detected" in item for item in warnings):
        return "blocked"
    if not rows:
        return "skipped"
    if any(not row.get("read_only") or row.get("auto_approved") or row.get("auto_closed") for row in rows):
        return "blocked"
    if any(row.get("unexpected_execution_flags") for row in rows):
        return "blocked"
    if any(row.get("status") in {"blocked", "failed"} for row in rows):
        return "blocked"
    if warnings:
        return "partial"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.1 Closure Evidence Index（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- report_count: {payload.get('report_count', 0)}",
        f"- latest_report: {payload.get('latest_report', '')}",
        "",
        "## Reports",
    ]
    for item in payload.get("reports", []):
        lines.append(
            f"- {item.get('path')}: {item.get('status')} | review_ready={item.get('review_ready_count', 0)} | missing={item.get('evidence_missing_count', 0)}"
        )
    lines.extend(["", "## Warnings"])
    warnings = payload.get("warnings", [])
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_closure_evidence_index(
    *,
    output_dir: str | Path | None = None,
    input_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = Path(input_dir) if input_dir else DEFAULT_INPUT_DIR

    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    if not source_root.exists():
        warnings.append(f"input_dir_not_found:{_to_rel(source_root)}")
    elif not source_root.is_dir():
        warnings.append(f"input_dir_not_directory:{_to_rel(source_root)}")
    else:
        for path in sorted(source_root.glob("*_launch_blocker_closure_workflow.json")):
            payload, load_warnings = _load_report(path)
            warnings.extend(load_warnings)
            if payload is not None:
                rows.append(_report_row(path, payload))

    rows.sort(key=lambda item: (str(item.get("generated_at", "")), str(item.get("modified_at", ""))), reverse=True)
    latest_report = rows[0]["path"] if rows else ""
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    status = _derive_status(rows, warnings)

    totals = {
        "closure_item_count": sum(int(row.get("closure_item_count", 0)) for row in rows),
        "review_ready_count": sum(int(row.get("review_ready_count", 0)) for row in rows),
        "evidence_missing_count": sum(int(row.get("evidence_missing_count", 0)) for row in rows),
        "evidence_incomplete_count": sum(int(row.get("evidence_incomplete_count", 0)) for row in rows),
        "blocked_closure_count": sum(int(row.get("blocked_closure_count", 0)) for row in rows),
        "skipped_closure_count": sum(int(row.get("skipped_closure_count", 0)) for row in rows),
    }
    latest_report_summary = {
        "closure_item_count": int(rows[0].get("closure_item_count", 0)) if rows else 0,
        "review_ready_count": int(rows[0].get("review_ready_count", 0)) if rows else 0,
        "evidence_missing_count": int(rows[0].get("evidence_missing_count", 0)) if rows else 0,
        "evidence_incomplete_count": int(rows[0].get("evidence_incomplete_count", 0)) if rows else 0,
        "blocked_closure_count": int(rows[0].get("blocked_closure_count", 0)) if rows else 0,
        "skipped_closure_count": int(rows[0].get("skipped_closure_count", 0)) if rows else 0,
        "closure_state_counts": rows[0].get("closure_state_counts", {}) if rows else {},
        "evidence_readiness_summary": rows[0].get("evidence_readiness_summary", {}) if rows else {},
    }

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.1.0-planning",
        "phase": "v4.1_phase_21.2",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "deployment_executed": False,
        "release_created": False,
        "tag_created": False,
        "auto_approved": False,
        "auto_closed": False,
        "source_root": _to_rel(source_root),
        "reports": rows,
        "report_count": len(rows),
        "latest_report": latest_report,
        "latest_report_summary": latest_report_summary,
        "totals": totals,
        "warnings": sorted(set(warnings)),
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "closure evidence index 只读汇总关闭工作流报告，不自动批准上线或关闭 blocker。",
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_closure_evidence_index"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "report_count": len(rows),
        "latest_report": latest_report,
        "warnings": sorted(set(warnings)),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.1 closure evidence 只读索引（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_closure_evidence_index(output_dir=args.output_dir, input_dir=args.input_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
