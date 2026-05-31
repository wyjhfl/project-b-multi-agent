from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "evidence_archive"

DEFAULT_EVIDENCE_ROOTS: dict[str, Path] = {
    "acceptance_snapshot": ROOT_DIR / "docs" / "reports" / "acceptance_snapshots",
    "demo_artifact": ROOT_DIR / "docs" / "reports" / "demo_artifacts",
    "failure_diagnostics": ROOT_DIR / "docs" / "reports" / "failure_diagnostics",
    "report_index": ROOT_DIR / "docs" / "reports" / "report_index",
    "config_drift": ROOT_DIR / "docs" / "reports" / "config_drift",
    "governance_policy": ROOT_DIR / "docs" / "reports" / "governance_policy",
    "live_drill_window": ROOT_DIR / "docs" / "reports" / "live_drill_window",
    "operator_workflow": ROOT_DIR / "docs" / "reports" / "operator_workflow",
    "incident_rehearsal": ROOT_DIR / "docs" / "reports" / "incident_rehearsal",
    "release_review": ROOT_DIR / "docs",
    "post_release_handoff": ROOT_DIR / "docs",
}

DOC_PATTERNS = {
    "release_review": "release_review_*.md",
    "post_release_handoff": "post_release_check_*.md",
}

BOUNDARY_DECLARATIONS = [
    "只读证据 manifest",
    "不删除文件",
    "不自动执行 retention 清理",
    "不读取报告内容",
    "不读取或输出真实 secret 原文",
    "不写业务数据",
    "默认 fake/offline",
    "不执行真实外网 LLM",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _to_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return str(path)


def _format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _iter_evidence_files(evidence_type: str, root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    pattern = DOC_PATTERNS.get(evidence_type)
    if pattern:
        return [p for p in root.glob(pattern) if p.is_file()]
    return [p for p in root.rglob("*") if p.is_file()]


def _file_item(evidence_type: str, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "evidence_type": evidence_type,
        "path": _to_rel(path),
        "size_bytes": stat.st_size,
        "modified_at": _format_ts(stat.st_mtime),
        "extension": path.suffix.lower(),
    }


def _derive_status(missing_expected_types: list[str], total_files: int) -> str:
    if total_files == 0:
        return "skipped"
    if missing_expected_types:
        return "warning"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.4 证据归档 Manifest（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- manifest_id: {payload.get('manifest_id', '')}",
        f"- status: {payload.get('status', '')}",
        f"- total_files: {payload.get('total_files', 0)}",
        f"- total_size_bytes: {payload.get('total_size_bytes', 0)}",
        "",
        "## Latest By Type",
    ]
    latest_by_type = payload.get("latest_by_type", {})
    for evidence_type, item in latest_by_type.items():
        lines.append(f"- {evidence_type}: {item.get('path', '') if isinstance(item, dict) else ''}")

    lines.extend(["", "## Missing Expected Types"])
    missing = payload.get("missing_expected_types", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_evidence_archive_manifest(
    *,
    output_dir: str | Path | None = None,
    evidence_roots: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    manifest_seed = f"{generated_at}|{commit}".encode("utf-8")
    manifest_id = "manifest-" + hashlib.sha256(manifest_seed).hexdigest()[:12]

    roots = {key: Path(value) for key, value in (evidence_roots or DEFAULT_EVIDENCE_ROOTS).items()}
    evidence_items: list[dict[str, Any]] = []
    latest_by_type: dict[str, dict[str, Any]] = {}
    missing_expected_types: list[str] = []
    evidence_root_rows: list[dict[str, Any]] = []

    for evidence_type, root in roots.items():
        files = sorted(_iter_evidence_files(evidence_type, root), key=lambda p: p.stat().st_mtime, reverse=True)
        evidence_root_rows.append(
            {
                "evidence_type": evidence_type,
                "root": _to_rel(root),
                "exists": root.exists(),
                "file_count": len(files),
            }
        )
        if not files:
            missing_expected_types.append(evidence_type)
            continue
        items = [_file_item(evidence_type, path) for path in files]
        evidence_items.extend(items)
        latest_by_type[evidence_type] = items[0]

    total_files = len(evidence_items)
    total_size_bytes = sum(int(item.get("size_bytes", 0)) for item in evidence_items)
    status = _derive_status(missing_expected_types, total_files)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.3.0",
        "manifest_id": manifest_id,
        "status": status,
        "evidence_roots": evidence_root_rows,
        "evidence_items": evidence_items,
        "latest_by_type": latest_by_type,
        "missing_expected_types": missing_expected_types,
        "total_files": total_files,
        "total_size_bytes": total_size_bytes,
        "retention_policy": {
            "apply_mode": "report_only",
            "deletion_enabled": False,
            "auto_cleanup_enabled": False,
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "read_only": True,
        "real_llm_executed": False,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_evidence_archive_manifest"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
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
        "output_dir": str(output_root),
        "manifest_id": manifest_id,
        "total_files": total_files,
        "missing_expected_types": missing_expected_types,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.4 只读证据归档 manifest（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_evidence_archive_manifest(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
