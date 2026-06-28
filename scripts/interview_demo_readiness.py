from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "interview_demo_readiness"
RUNBOOK_PATH = "docs/interview_demo_readiness_v50.md"

SECRET_TEXT_PATTERNS = (
    re.compile("s" + r"k-[A-Za-z0-9_\-]{8,}"),
    re.compile("t" + r"p-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
)

RESUME_MATERIAL_CHECKS = {
    "readme": (
        ROOT_DIR / "README.md",
        ("Multi-Agent Runtime", "Trajectory", "public_production_direct_launch"),
    ),
    "resume_pack": (
        ROOT_DIR / "docs" / "resume_interview_optimization_pack_v50.md",
        ("Resume", "2-minute Pitch", "trajectory visualization"),
    ),
    "interview_guide": (
        ROOT_DIR / "docs" / "interview_guide.md",
        ("Interview Guide", "Agent"),
    ),
    "architecture": (
        ROOT_DIR / "docs" / "architecture.md",
        ("Architecture", "Agent"),
    ),
}

FRONTEND_CHECKS = {
    "observability_page": (
        ROOT_DIR / "frontend" / "src" / "app" / "observability" / "page.tsx",
        ("Multi-Agent 轨迹", "getTaskTrajectory", "trajectory.steps"),
    ),
    "operations_page": (
        ROOT_DIR / "frontend" / "src" / "app" / "operations" / "page.tsx",
        ("Landing Command Center", "Operator Guidance"),
    ),
}

DEMO_PATH_CHECKS = {
    "demo_up": ROOT_DIR / "scripts" / "demo_up.ps1",
    "demo_smoke": ROOT_DIR / "scripts" / "demo_smoke.ps1",
    "demo_down": ROOT_DIR / "scripts" / "demo_down.ps1",
    "interview_readiness_script": ROOT_DIR / "scripts" / "interview_demo_readiness.py",
    "interview_readiness_runbook": ROOT_DIR / RUNBOOK_PATH,
}

RECOMMENDED_COMMANDS = [
    {
        "id": "run_interview_readiness",
        "label": "Run read-only interview/demo readiness check",
        "command": "python scripts/interview_demo_readiness.py",
        "safe_boundary": "read_only_no_secret_plaintext",
    },
    {
        "id": "start_local_demo",
        "label": "Start local Docker demo",
        "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1",
        "safe_boundary": "local_demo_no_secret_plaintext",
    },
    {
        "id": "run_demo_smoke",
        "label": "Run local demo smoke check",
        "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1",
        "safe_boundary": "local_read_only_smoke",
    },
    {
        "id": "run_focused_tests",
        "label": "Run focused Multi-Agent showcase tests",
        "command": "python -m pytest tests/test_multi_agent_v03.py tests/test_multi_agent_trajectory_v11.py tests/test_trajectory_eval_v11.py tests/test_operations_summary_v312.py -q",
        "safe_boundary": "default_fake_offline",
    },
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _check_text_file(check_id: str, path: Path, required_markers: tuple[str, ...]) -> dict[str, Any]:
    rel_path = str(path.relative_to(ROOT_DIR))
    if not path.exists() or not path.is_file():
        return {
            "id": check_id,
            "path": rel_path,
            "status": "missing",
            "present": False,
            "missing_markers": list(required_markers),
            "secret_like_detected": False,
        }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {
            "id": check_id,
            "path": rel_path,
            "status": "blocked",
            "present": True,
            "missing_markers": list(required_markers),
            "secret_like_detected": False,
        }
    missing = [marker for marker in required_markers if marker not in text]
    secret_like_detected = _contains_secret_like(text)
    status = "success" if not missing and not secret_like_detected else "partial"
    if secret_like_detected:
        status = "blocked"
    return {
        "id": check_id,
        "path": rel_path,
        "status": status,
        "present": True,
        "missing_markers": missing,
        "secret_like_detected": secret_like_detected,
    }


def _check_path_exists(check_id: str, path: Path) -> dict[str, Any]:
    return {
        "id": check_id,
        "path": str(path.relative_to(ROOT_DIR)),
        "status": "success" if path.exists() else "missing",
        "present": path.exists(),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 面试演示就绪检查",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- status: {payload['status']}",
        f"- interview_demo_ready: {payload['interview_demo_ready']}",
        f"- public_production_direct_launch: {payload['public_production_direct_launch']}",
        f"- secret_plaintext_output: {payload['secret_plaintext_output']}",
        "",
        "## 推荐命令",
    ]
    for command in payload["recommended_commands"]:
        lines.extend([
            "",
            f"### {command['id']}",
            "",
            f"- label: {command['label']}",
            f"- safe_boundary: {command['safe_boundary']}",
            "",
            "```powershell",
            command["command"],
            "```",
        ])
    lines.extend(["", "## 缺口"])
    if payload["missing_conditions"]:
        lines.extend(f"- {item}" for item in payload["missing_conditions"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_interview_demo_readiness(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = (_run_git(["rev-parse", "--short", "HEAD"]) or "unknown")[:8]

    resume_checks = [_check_text_file(check_id, path, markers) for check_id, (path, markers) in RESUME_MATERIAL_CHECKS.items()]
    frontend_checks = [_check_text_file(check_id, path, markers) for check_id, (path, markers) in FRONTEND_CHECKS.items()]
    demo_path_checks = [_check_path_exists(check_id, path) for check_id, path in DEMO_PATH_CHECKS.items()]

    missing_conditions: list[str] = []
    for section_id, checks in (("resume_material", resume_checks), ("frontend", frontend_checks), ("demo_path", demo_path_checks)):
        for check in checks:
            if check["status"] != "success":
                missing_conditions.append(f"{section_id}:{check['id']}:{check['status']}")
            if check.get("secret_like_detected"):
                missing_conditions.append(f"{section_id}:{check['id']}:secret_like_detected")

    resume_material_ready = all(check["status"] == "success" for check in resume_checks)
    frontend_ready = all(check["status"] == "success" for check in frontend_checks)
    demo_path_ready = all(check["status"] == "success" for check in demo_path_checks)
    secret_plaintext_output = any(bool(check.get("secret_like_detected")) for check in [*resume_checks, *frontend_checks])
    interview_demo_ready = resume_material_ready and frontend_ready and demo_path_ready and not secret_plaintext_output
    status = "success" if interview_demo_ready and not missing_conditions else "partial"
    if secret_plaintext_output:
        status = "blocked"

    payload: dict[str, Any] = {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "read_only_interview_demo_readiness",
        "runbook_path": RUNBOOK_PATH,
        "resume_material_ready": resume_material_ready,
        "frontend_ready": frontend_ready,
        "demo_path_ready": demo_path_ready,
        "interview_demo_ready": interview_demo_ready,
        "public_production_direct_launch": "No-Go",
        "real_business_system_connected": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": secret_plaintext_output,
        "missing_conditions": missing_conditions,
        "resume_material_checks": resume_checks,
        "frontend_checks": frontend_checks,
        "demo_path_checks": demo_path_checks,
        "recommended_commands": RECOMMENDED_COMMANDS,
    }

    report_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_interview_demo_readiness"
    json_path = report_dir / f"{stem}.json"
    markdown_path = report_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "interview_demo_ready": interview_demo_ready,
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": secret_plaintext_output,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build read-only interview demo readiness evidence.")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    summary = build_interview_demo_readiness(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
