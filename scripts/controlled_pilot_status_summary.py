from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_status_summary"
REPORTS = {
    "production_pilot_bootstrap": (
        ROOT_DIR / "docs" / "reports" / "production_pilot_bootstrap",
        "*_production_pilot_bootstrap.json",
    ),
    "production_pilot_evidence_bundle": (
        ROOT_DIR / "docs" / "reports" / "production_pilot_evidence_bundle",
        "*_production_pilot_evidence_bundle.json",
    ),
    "controlled_pilot_launch_gate": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_gate",
        "*_controlled_pilot_launch_gate.json",
    ),
    "controlled_pilot_launch_package": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_package",
        "*_controlled_pilot_launch_package.json",
    ),
    "controlled_pilot_window_status": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_status",
        "*_controlled_pilot_window_status.json",
    ),
    "operations_console_landing_smoke": (
        ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke",
        "*_operations_console_landing_smoke.json",
    ),
    "business_system_read_smoke": (
        ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
        "*_business_system_read_smoke.json",
    ),
    "business_system_production_readiness": (
        ROOT_DIR / "docs" / "reports" / "business_system_production_readiness",
        "*_business_system_production_readiness.json",
    ),
    "production_landing_evidence_freshness": (
        ROOT_DIR / "docs" / "reports" / "production_landing_evidence_freshness",
        "*_production_landing_evidence_freshness.json",
    ),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(path: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return str(payload.get("generated_at") or ""), path.stat().st_mtime, path.name

    return max(files, key=sort_key)


def _load_latest(
    report_id: str,
    reports: dict[str, tuple[Path, str]],
) -> tuple[Path | None, dict[str, Any]]:
    directory, pattern = reports[report_id]
    path = _latest_json(directory, pattern)
    if path is None:
        return None, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}
    return path, payload if isinstance(payload, dict) else {}


def _load_latest_successful_executed_operations_smoke(
    reports: dict[str, tuple[Path, str]],
) -> tuple[Path | None, dict[str, Any]]:
    directory, pattern = reports["operations_console_landing_smoke"]
    if not directory.exists() or not directory.is_dir():
        return None, {}
    candidates: list[tuple[str, float, Path, dict[str, Any]]] = []
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "success" and payload.get("execute") is True:
            candidates.append((str(payload.get("generated_at") or ""), path.stat().st_mtime, path, payload))
    if not candidates:
        return None, {}
    _, _, path, payload = max(candidates, key=lambda item: (item[0], item[1], item[2].name))
    return path, payload


def _controlled_pilot(payload: dict[str, Any]) -> str:
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    return str(payload.get("controlled_pilot") or go_no_go.get("controlled_pilot") or "")


def _report_row(report_id: str, path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": path is not None,
        "latest_json_path": str(path or ""),
        "selection": "latest_successful_executed" if report_id == "operations_console_landing_smoke" else "latest",
        "status": str(payload.get("status") or "missing"),
        "generated_at": str(payload.get("generated_at") or ""),
        "controlled_pilot": _controlled_pilot(payload),
        "ready_for_controlled_pilot": payload.get("ready_for_controlled_pilot"),
        "launch_package_ready": payload.get("launch_package_ready"),
        "controlled_pilot_ready": payload.get("controlled_pilot_ready"),
        "operations_console_smoke_status": payload.get("operations_console_smoke_status"),
        "business_read_executed": payload.get("business_read_executed"),
        "business_system_connected": payload.get("business_system_connected"),
        "business_public_production_gap": (
            payload.get("env_profile", {}).get("public_production_gap")
            if isinstance(payload.get("env_profile"), dict)
            else None
        ),
        "production_readiness_status": payload.get("status")
        if report_id == "business_system_production_readiness"
        else None,
        "production_readiness_missing_count": payload.get("missing_condition_count")
        if report_id == "business_system_production_readiness"
        else None,
        "evidence_freshness_status": payload.get("status")
        if report_id == "production_landing_evidence_freshness"
        else None,
        "worktree_clean": payload.get("worktree_clean")
        if report_id == "production_landing_evidence_freshness"
        else None,
        "source_count": payload.get("source_count")
        if report_id == "production_landing_evidence_freshness"
        else None,
        "stale_source_count": payload.get("stale_source_count")
        if report_id == "production_landing_evidence_freshness"
        else None,
        "runtime_smoke_passed": payload.get("runtime_smoke_passed"),
        "missing_condition_count": payload.get("missing_condition_count"),
        "public_production_direct_launch": payload.get("public_production_direct_launch")
        or (payload.get("go_no_go") or {}).get("public_production_direct_launch")
        or "No-Go",
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def build_controlled_pilot_status_summary(
    *,
    report_dirs: dict[str, str | Path] | None = None,
    output_dir: str | Path | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    effective_reports = {
        report_id: (Path(report_dirs[report_id]), config[1]) if report_dirs and report_id in report_dirs else config
        for report_id, config in REPORTS.items()
    }
    reports: dict[str, dict[str, Any]] = {}
    for report_id in effective_reports:
        path, payload = _load_latest(report_id, effective_reports)
        if report_id == "operations_console_landing_smoke":
            evidence_path, evidence_payload = _load_latest_successful_executed_operations_smoke(effective_reports)
            if evidence_payload:
                path, payload = evidence_path, evidence_payload
        reports[report_id] = _report_row(report_id, path, payload)

    blocking = [
        report_id
        for report_id, report in reports.items()
        if report["present"] is not True
        or report["secret_plaintext_output"] is True
        or report["public_production_direct_launch"] != "No-Go"
        or report["status"] in {"blocked", "failed", "missing"}
    ]
    public_production_gaps: list[str] = []
    business_report = reports.get("business_system_read_smoke", {})
    if business_report.get("business_read_executed") is not True:
        public_production_gaps.append("business_system:real_read_only_smoke_not_executed")
    if business_report.get("business_public_production_gap") is True:
        public_production_gaps.append("business_system:public_production_gap")
    business_readiness = reports.get("business_system_production_readiness", {})
    if business_readiness.get("production_readiness_status") != "ready":
        public_production_gaps.append("business_system:production_readiness_not_ready")
    evidence_freshness = reports.get("production_landing_evidence_freshness", {})
    freshness_ready = (
        evidence_freshness.get("evidence_freshness_status") == "success"
        and evidence_freshness.get("worktree_clean") is True
        and int(evidence_freshness.get("stale_source_count") or 0) == 0
        and evidence_freshness.get("secret_plaintext_output") is not True
    )
    if not freshness_ready and "production_landing_evidence_freshness" not in blocking:
        blocking.append("production_landing_evidence_freshness")

    ready = (
        not blocking
        and not public_production_gaps
        and reports["controlled_pilot_launch_gate"]["status"] == "ready"
        and reports["controlled_pilot_launch_gate"]["ready_for_controlled_pilot"] is True
        and reports["controlled_pilot_launch_package"]["status"] == "ready"
        and reports["controlled_pilot_launch_package"]["launch_package_ready"] is True
        and reports["controlled_pilot_window_status"]["status"] == "healthy"
        and reports["operations_console_landing_smoke"]["status"] == "success"
        and business_report.get("business_read_executed") is True
        and business_readiness.get("production_readiness_status") == "ready"
    )
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.15",
        "phase": "v4.8 Controlled Pilot Status Summary",
        "mode": "read_only_status_summary",
        "status": "ready" if ready else "partial",
        "controlled_internal_pilot": "Go" if ready else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "reports": reports,
        "blocking_reports": blocking,
        "public_production_gaps": sorted(set(public_production_gaps)),
        "public_production_gap_count": len(set(public_production_gaps)),
    }
    if write_report:
        output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        output_root.mkdir(parents=True, exist_ok=True)
        short_commit = commit[:8] if commit != "unknown" else "unknown"
        stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_status_summary"
        json_path = output_root / f"{stem}.json"
        markdown_path = output_root / f"{stem}.md"
        payload["json_path"] = str(json_path)
        payload["markdown_path"] = str(markdown_path)
        payload["output_dir"] = str(output_root)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 受控试点总状态摘要",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- controlled_internal_pilot: {payload.get('controlled_internal_pilot', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 报告来源",
    ]
    for report_id, report in payload.get("reports", {}).items():
        lines.append(
            f"- {report_id}: status={report.get('status')} selection={report.get('selection')} "
            f"path={report.get('latest_json_path')}"
        )
    lines.extend(["", "## 阻断报告"])
    blocking = payload.get("blocking_reports", [])
    lines.extend(f"- {item}" for item in blocking) if blocking else lines.append("- none")
    lines.extend(["", "## 公网生产缺口"])
    public_gaps = payload.get("public_production_gaps", [])
    lines.extend(f"- {item}" for item in public_gaps) if public_gaps else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the latest controlled pilot landing status.")
    parser.add_argument("--json", action="store_true", help="Print full JSON instead of a compact table.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    summary = build_controlled_pilot_status_summary(output_dir=args.output_dir, write_report=not args.no_write_report)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"status={summary['status']}")
    print(f"controlled_internal_pilot={summary['controlled_internal_pilot']}")
    print(f"public_production_direct_launch={summary['public_production_direct_launch']}")
    print(f"secret_plaintext_output={summary['secret_plaintext_output']}")
    for report_id, report in summary["reports"].items():
        print(
            f"{report_id}: status={report['status']} missing={report['missing_condition_count']} "
            f"public={report['public_production_direct_launch']} secret={report['secret_plaintext_output']}"
        )
    if summary.get("json_path"):
        print(f"json_path={summary['json_path']}")
        print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
