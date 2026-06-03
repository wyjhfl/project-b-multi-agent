from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "pilot_evidence_comparison"
DEFAULT_BASELINE = ROOT_DIR / "docs" / "reports" / "evidence_archive" / "baseline"
DEFAULT_CURRENT = ROOT_DIR / "docs" / "reports" / "evidence_archive" / "current"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

BOUNDARY_DECLARATIONS = [
    "只读对比快照",
    "不删除、不移动、不修改输入证据",
    "仅写 output-dir 下报告",
    "不读取报告正文内容",
    "输入为 manifest JSON 时仅读取元数据",
    "输入为目录时仅列文件元数据",
    "不读取或输出真实 secret 原文",
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


def _load_manifest_items(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], [f"manifest_parse_failed:{path.name}:{type(exc).__name__}"]
    raw_items = payload.get("evidence_items")
    if not isinstance(raw_items, list):
        return [], [f"manifest_missing_evidence_items:{path.name}"]

    items: list[dict[str, Any]] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        rel_path = str(row.get("path", ""))
        if not rel_path:
            continue
        items.append(
            {
                "evidence_type": str(row.get("evidence_type", "")),
                "path": rel_path,
                "size_bytes": int(row.get("size_bytes", 0) or 0),
                "modified_at": str(row.get("modified_at", "")),
                "extension": str(row.get("extension", "")),
            }
        )
    if not items:
        warnings.append(f"manifest_empty_items:{path.name}")
    return items, warnings


def _load_dir_items(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return [], [f"path_not_found:{_to_rel(path)}"]
    if not path.is_dir():
        return [], [f"path_not_directory:{_to_rel(path)}"]
    files = [p for p in path.rglob("*") if p.is_file()]
    if not files:
        return [], [f"directory_empty:{_to_rel(path)}"]

    items: list[dict[str, Any]] = []
    for file in files:
        stat = file.stat()
        items.append(
            {
                "evidence_type": "directory_file",
                "path": _to_rel(file),
                "size_bytes": stat.st_size,
                "modified_at": _format_ts(stat.st_mtime),
                "extension": file.suffix.lower(),
            }
        )
    return items, warnings


def _load_input(path: Path) -> tuple[list[dict[str, Any]], str, list[str]]:
    if path.suffix.lower() == ".json" and path.is_file():
        items, warnings = _load_manifest_items(path)
        return items, "manifest_json", warnings
    items, warnings = _load_dir_items(path)
    return items, "evidence_directory", warnings


def _build_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        key = str(item.get("path", ""))
        if not key:
            continue
        index[key] = item
    return index


def _derive_status(*, baseline_ready: bool, current_ready: bool, warnings: list[str]) -> str:
    if not baseline_ready or not current_ready:
        return "skipped"
    if warnings:
        return "partial"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    diff = payload.get("comparison", {})
    lines = [
        "# v3.5 Pilot Evidence Comparison Snapshot（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- baseline_source_type: {payload.get('baseline_source_type', '')}",
        f"- current_source_type: {payload.get('current_source_type', '')}",
        f"- added_count: {diff.get('added_count', 0)}",
        f"- removed_count: {diff.get('removed_count', 0)}",
        f"- changed_count: {diff.get('changed_count', 0)}",
        "",
        "## Warnings",
    ]
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


def build_pilot_evidence_comparison(
    *,
    output_dir: str | Path | None = None,
    baseline: str | Path | None = None,
    current: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    baseline_path = Path(baseline) if baseline else DEFAULT_BASELINE
    current_path = Path(current) if current else DEFAULT_CURRENT

    warnings: list[str] = []
    baseline_items, baseline_source_type, baseline_warnings = _load_input(baseline_path)
    current_items, current_source_type, current_warnings = _load_input(current_path)
    warnings.extend(baseline_warnings)
    warnings.extend(current_warnings)

    baseline_ready = len(baseline_items) > 0
    current_ready = len(current_items) > 0
    if baseline is None:
        warnings.append("baseline_not_provided_use_default")
    if current is None:
        warnings.append("current_not_provided_use_default")

    baseline_index = _build_index(baseline_items)
    current_index = _build_index(current_items)

    baseline_keys = set(baseline_index)
    current_keys = set(current_index)
    added = sorted(current_keys - baseline_keys)
    removed = sorted(baseline_keys - current_keys)
    changed: list[dict[str, Any]] = []
    for key in sorted(baseline_keys & current_keys):
        b_item = baseline_index[key]
        c_item = current_index[key]
        b_sig = (b_item.get("size_bytes"), b_item.get("modified_at"), b_item.get("extension"))
        c_sig = (c_item.get("size_bytes"), c_item.get("modified_at"), c_item.get("extension"))
        if b_sig != c_sig:
            changed.append({"path": key, "baseline": b_item, "current": c_item})

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    status = _derive_status(baseline_ready=baseline_ready, current_ready=current_ready, warnings=warnings)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "baseline_input": str(baseline_path),
        "current_input": str(current_path),
        "baseline_source_type": baseline_source_type,
        "current_source_type": current_source_type,
        "baseline_total_files": len(baseline_items),
        "current_total_files": len(current_items),
        "comparison": {
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "added_paths": added,
            "removed_paths": removed,
            "changed_items": changed,
        },
        "warnings": warnings,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_pilot_evidence_comparison"
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
        "warnings": warnings,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.5 Pilot evidence comparison snapshot（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--current", default=str(DEFAULT_CURRENT))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_pilot_evidence_comparison(
        output_dir=args.output_dir,
        baseline=args.baseline,
        current=args.current,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
