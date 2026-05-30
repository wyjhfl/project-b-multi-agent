from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "report_index"
DEFAULT_REPORT_ROOTS: dict[str, Path] = {
    "acceptance_snapshot": ROOT_DIR / "docs" / "reports" / "acceptance_snapshots",
    "demo_artifact": ROOT_DIR / "docs" / "reports" / "demo_artifacts",
    "failure_diagnostics": ROOT_DIR / "docs" / "reports" / "failure_diagnostics",
}

BOUNDARY_DECLARATIONS = [
    "read only index: no file deletion",
    "no user data deletion",
    "no report auto cleanup",
    "fake/offline default",
    "no real external LLM execution",
    "no raw prompt / no secrets",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


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


def _iter_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def _build_report_type_entry(
    *,
    report_type: str,
    report_root: Path,
    files: list[Path],
    retention_keep_latest: int,
    retention_days: int,
) -> dict[str, Any]:
    sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    total_size = sum(p.stat().st_size for p in sorted_files)

    latest_path = _to_rel(sorted_files[0]) if sorted_files else ""
    latest_generated_at = _format_ts(sorted_files[0].stat().st_mtime) if sorted_files else ""

    stale: list[dict[str, Any]] = []
    cutoff = _utc_now() - timedelta(days=max(0, retention_days))
    for idx, path in enumerate(sorted_files):
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        reasons: list[str] = []
        if idx >= max(0, retention_keep_latest):
            reasons.append("over_keep_latest")
        if mtime < cutoff:
            reasons.append("older_than_retain_days")
        if reasons:
            stale.append(
                {
                    "path": _to_rel(path),
                    "size_bytes": path.stat().st_size,
                    "modified_at": mtime.isoformat(),
                    "reasons": reasons,
                }
            )

    return {
        "report_type": report_type,
        "report_root": _to_rel(report_root),
        "file_count": len(sorted_files),
        "latest_generated_at": latest_generated_at,
        "latest_path": latest_path,
        "total_size_bytes": total_size,
        "stale_candidates": stale,
        "retention_policy": {
            "keep_latest": max(0, retention_keep_latest),
            "retain_days": max(0, retention_days),
            "apply_mode": "report_only",
            "deletion_enabled": False,
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Report Index & Retention Summary (Read Only)",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        "",
        "## Report Types",
    ]
    for item in payload.get("report_index", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {item.get('report_type', 'unknown')}",
                f"- report_root: {item.get('report_root', '')}",
                f"- file_count: {item.get('file_count', 0)}",
                f"- latest_generated_at: {item.get('latest_generated_at', '')}",
                f"- latest_path: {item.get('latest_path', '')}",
                f"- total_size_bytes: {item.get('total_size_bytes', 0)}",
                f"- stale_candidates_count: {len(item.get('stale_candidates', []))}",
                f"- retention_policy: {json.dumps(item.get('retention_policy', {}), ensure_ascii=False)}",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary Declarations",
            "- read only index: no file deletion",
            "- no user data deletion",
            "- no report auto cleanup",
            "- fake/offline default",
            "- no real external LLM execution",
            "",
        ]
    )
    return "\n".join(lines)


def build_report_index(
    *,
    output_dir: str | Path | None = None,
    report_roots: dict[str, str | Path] | None = None,
    retention_keep_latest: int = 20,
    retention_days: int = 30,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    resolved_roots: dict[str, Path] = {}
    for key, value in (report_roots or DEFAULT_REPORT_ROOTS).items():
        resolved_roots[key] = Path(value)

    report_index: list[dict[str, Any]] = []
    for report_type, root in resolved_roots.items():
        files = _iter_files(root)
        report_index.append(
            _build_report_type_entry(
                report_type=report_type,
                report_root=root,
                files=files,
                retention_keep_latest=retention_keep_latest,
                retention_days=retention_days,
            )
        )

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "report_root": _to_rel(ROOT_DIR / "docs" / "reports"),
        "retention_policy": {
            "keep_latest": max(0, retention_keep_latest),
            "retain_days": max(0, retention_days),
            "apply_mode": "report_only",
            "deletion_enabled": False,
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "report_index": report_index,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_report_index"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": "ok",
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "report_types": list(resolved_roots.keys()),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only report index and retention candidates (JSON + Markdown)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--keep-latest", type=int, default=20)
    parser.add_argument("--retain-days", type=int, default=30)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_report_index(
        output_dir=args.output_dir,
        retention_keep_latest=args.keep_latest,
        retention_days=args.retain_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
