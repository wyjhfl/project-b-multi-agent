from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "operator_workflow"

BOUNDARY_DECLARATIONS = [
    "默认 fake/offline",
    "默认 pytest/CI 不调用真实 LLM",
    "只读索引，不写业务数据",
    "不删除用户数据",
    "不自动清理报告",
    "不修改 .env",
    "不读取或输出真实 secret 原文",
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


def _entry_exists(entry: dict[str, Any]) -> bool:
    checks = entry.get("local_checks", [])
    if not checks:
        return True
    return all((ROOT_DIR / item).exists() for item in checks)


def _build_entries() -> list[dict[str, Any]]:
    return [
        {
            "entry_id": "operations_console",
            "name": "/operations 只读运营总览",
            "entry": "/operations",
            "when_to_use": "日常查看 health、deployment、metrics、tasks、approvals、audit、pilot reports 与演示证据摘要。",
            "default_output_dir": "",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "页面或 `/operations/summary` 不可用时说明服务未启动或后端不可达；空数据不代表成功，只表示当前无可展示证据。",
            "runbook_path": "docs/operations_troubleshooting_index_v31.md",
            "local_checks": ["frontend/src/app/operations/page.tsx", "app/api/operations.py"],
        },
        {
            "entry_id": "acceptance_snapshot",
            "name": "Acceptance Snapshot",
            "entry": "python scripts/acceptance_snapshot.py --output-dir docs/reports/acceptance_snapshots",
            "when_to_use": "需要生成验收快照，汇总 health、deployment、operations、metrics、audit、pilot reports、demo evidence 状态时使用。",
            "default_output_dir": "docs/reports/acceptance_snapshots/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "服务未启动时在线检查标记为 skipped，不伪造成成功。",
            "runbook_path": "docs/acceptance_snapshot_runbook_v32.md",
            "local_checks": ["scripts/acceptance_snapshot.py", "docs/acceptance_snapshot_runbook_v32.md"],
        },
        {
            "entry_id": "demo_artifact_bundle",
            "name": "Demo Artifact Bundle",
            "entry": "powershell -File scripts/demo_e2e.ps1 -ArtifactDir docs/reports/demo_artifacts",
            "when_to_use": "需要归档离线演示 seed、在线 smoke、operations summary、pilot report index 与 acceptance snapshot 证据时使用。",
            "default_output_dir": "docs/reports/demo_artifacts/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "服务不可用时 online smoke 记录为 skipped，不把不可达场景记为成功。",
            "runbook_path": "docs/demo_artifact_bundle_runbook_v32.md",
            "local_checks": ["scripts/demo_e2e.ps1", "scripts/demo_artifact_bundle.py", "docs/demo_artifact_bundle_runbook_v32.md"],
        },
        {
            "entry_id": "failure_diagnostics",
            "name": "Failure Diagnostics",
            "entry": "python scripts/failure_diagnostics.py --output-dir docs/reports/failure_diagnostics",
            "when_to_use": "需要排查 compose、deployment guard、OIDC、audit export、demo/acceptance skipped、pilot reports empty、real LLM opt-in skipped 等失败线索时使用。",
            "default_output_dir": "docs/reports/failure_diagnostics/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "blocked 表示需要先处理前置条件；skipped 表示缺少可选条件；partial 表示部分在线检查不可用。",
            "runbook_path": "docs/failure_diagnostics_pack_v32.md",
            "local_checks": ["scripts/failure_diagnostics.py", "docs/failure_diagnostics_pack_v32.md"],
        },
        {
            "entry_id": "report_index",
            "name": "Report Index",
            "entry": "python scripts/report_index.py --output-dir docs/reports/report_index",
            "when_to_use": "需要列出报告产物、最新文件与 stale candidates，但不执行清理时使用。",
            "default_output_dir": "docs/reports/report_index/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "空目录表示暂无对应报告；stale candidates 仅为候选提示，不会自动删除。",
            "runbook_path": "docs/report_index_retention_runbook_v33.md",
            "local_checks": ["scripts/report_index.py", "docs/report_index_retention_runbook_v33.md"],
        },
        {
            "entry_id": "config_drift",
            "name": "Config Drift",
            "entry": "python scripts/config_drift_check.py --output-dir docs/reports/config_drift",
            "when_to_use": "需要比较配置模板键漂移、记录缺失或新增配置项，但不修改 `.env` 时使用。",
            "default_output_dir": "docs/reports/config_drift/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "warning 表示需要人工复核配置模板差异；脚本不自动修复。",
            "runbook_path": "docs/config_drift_checklist_v33.md",
            "local_checks": ["scripts/config_drift_check.py", "docs/config_drift_checklist_v33.md"],
        },
        {
            "entry_id": "governance_summary",
            "name": "Governance Summary",
            "entry": "python scripts/governance_policy_summary.py --output-dir docs/reports/governance_policy",
            "when_to_use": "需要汇总默认 fake/offline、真实 LLM opt-in、secret、OIDC、report retention、config drift、release/tag 边界时使用。",
            "default_output_dir": "docs/reports/governance_policy/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "缺少证据路径时需要人工补齐；摘要不代表生产级安全或 SSO 验收完成。",
            "runbook_path": "docs/governance_policy_summary_v33.md",
            "local_checks": ["scripts/governance_policy_summary.py", "docs/governance_policy_summary_v33.md"],
        },
        {
            "entry_id": "live_drill_window",
            "name": "Live Drill Window",
            "entry": "python scripts/live_drill_window.py --output-dir docs/reports/live_drill_window",
            "when_to_use": "需要在可选真实 LLM/OIDC 演练窗口前做只读预检，确认缺失条件与服务窗口状态时使用。",
            "default_output_dir": "docs/reports/live_drill_window/",
            "read_only": True,
            "real_llm_executed": False,
            "failure_or_skipped_interpretation": "缺少真实 LLM 或 OIDC opt-in 条件时必须 skipped；服务不可达时 partial；脚本不执行真实外网 LLM。",
            "runbook_path": "docs/live_drill_window_v33.md",
            "local_checks": ["scripts/live_drill_window.py", "docs/live_drill_window_v33.md"],
        },
    ]


def _derive_status(entries: list[dict[str, Any]]) -> str:
    missing = [entry for entry in entries if not entry.get("available", False)]
    if missing:
        return "partial"
    return "ok"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.4 操作员工作流索引（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- mode: {payload.get('mode', '')}",
        "",
        "## 日常入口",
    ]
    for entry in payload.get("entries", []):
        lines.extend(
            [
                f"### {entry.get('name', '')}",
                f"- entry: {entry.get('entry', '')}",
                f"- when_to_use: {entry.get('when_to_use', '')}",
                f"- default_output_dir: {entry.get('default_output_dir', '')}",
                f"- read_only: {entry.get('read_only', True)}",
                f"- real_llm_executed: {entry.get('real_llm_executed', False)}",
                f"- failure_or_skipped_interpretation: {entry.get('failure_or_skipped_interpretation', '')}",
                f"- runbook_path: {entry.get('runbook_path', '')}",
                f"- available: {entry.get('available', False)}",
                "",
            ]
        )

    lines.extend(["## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_operator_workflow_index(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    entries = _build_entries()
    for entry in entries:
        entry["available"] = _entry_exists(entry)

    missing_entries = [entry["entry_id"] for entry in entries if not entry["available"]]
    status = _derive_status(entries)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "mode": "fake_offline_default",
        "status": status,
        "read_only": True,
        "real_llm_executed": False,
        "entries": entries,
        "missing_entries": missing_entries,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_operator_workflow_index"
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
        "entry_count": len(entries),
        "missing_entries": missing_entries,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.4 操作员工作流只读索引（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_operator_workflow_index(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
