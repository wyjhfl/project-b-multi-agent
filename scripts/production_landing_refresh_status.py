from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from scripts.production_landing_action_pack import build_production_landing_action_pack
from scripts.production_landing_blocker_resolution import build_production_landing_blocker_resolution
from scripts.production_landing_execution_gate import build_production_landing_execution_gate
from scripts.production_landing_final_verification import build_production_landing_final_verification
from scripts.business_system_input_packet import build_business_system_input_packet
from scripts.business_system_landing_execution_pack import build_business_system_landing_execution_pack
from scripts.business_system_production_readiness_brief import build_business_system_production_readiness_brief
from scripts.production_landing_input_readiness import (
    DEFAULT_CLOSURE_EVIDENCE,
    build_production_landing_input_readiness,
)
from scripts.manual_signoff_evidence_ack_status import build_manual_signoff_evidence_ack_status
from scripts.manual_signoff_record_promote import build_manual_signoff_record_promote
from scripts.manual_signoff_record_validator import build_manual_signoff_record_validation
from scripts.operations_console_landing_smoke import build_operations_console_landing_smoke
from scripts.production_landing_text_quality_check import build_production_landing_text_quality_check
from scripts.production_landing_status import build_production_landing_status
from scripts.production_pilot_signoff_summary import build_production_pilot_signoff_summary
from scripts.real_integration_gap_register import build_real_integration_gap_register
from scripts.real_integration_staging_gate import build_real_integration_staging_gate
from scripts.real_production_environment_checklist import build_real_production_environment_checklist

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_refresh_status"
STATUS_VOCABULARY = {"success", "skipped", "blocked", "partial", "failed"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _safe_step_summary(step_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    status = str(summary.get("status") or "skipped")
    if status not in STATUS_VOCABULARY:
        status = "skipped"
    return {
        "step_id": step_id,
        "status": status,
        "generated_at": str(summary.get("generated_at") or ""),
        "json_path": str(summary.get("json_path") or ""),
        "markdown_path": str(summary.get("markdown_path") or ""),
        "secret_plaintext_output": bool(summary.get("secret_plaintext_output", False)),
    }


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing refresh status",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- final_status: {payload.get('final_status', '')}",
        f"- blocker_count: {payload.get('blocker_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Steps",
    ]
    for item in payload.get("steps", []):
        lines.append(f"- {item.get('step_id')}: {item.get('status')} | {item.get('json_path')}")
    lines.extend(["", "## Final Blockers"])
    blockers = payload.get("final_blockers", [])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_refresh_status(
    *,
    output_dir: str | Path | None = None,
    env_path: str | Path | None = None,
    closure_evidence: str | Path | None = None,
    builders: dict[str, Callable[..., dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_builders: dict[str, Callable[..., dict[str, Any]]] = {
        "execution_gate": build_production_landing_execution_gate,
        "real_integration_staging_gate": build_real_integration_staging_gate,
        "real_integration_gap_register": build_real_integration_gap_register,
        "real_production_environment_checklist": build_real_production_environment_checklist,
        "business_system_input_packet": build_business_system_input_packet,
        "business_system_production_readiness": build_business_system_production_readiness_brief,
        "business_system_landing_execution_pack": build_business_system_landing_execution_pack,
        "production_landing_input_readiness": build_production_landing_input_readiness,
        "manual_signoff_evidence_ack_status": build_manual_signoff_evidence_ack_status,
        "manual_signoff_record_validation": build_manual_signoff_record_validation,
        "manual_signoff_record_promote": build_manual_signoff_record_promote,
        "operations_console_landing_smoke": build_operations_console_landing_smoke,
        "production_landing_text_quality": build_production_landing_text_quality_check,
        "production_pilot_signoff": build_production_pilot_signoff_summary,
        "production_landing_action_pack": build_production_landing_action_pack,
        "production_landing_blocker_resolution": build_production_landing_blocker_resolution,
        "production_landing_status": build_production_landing_status,
        "production_landing_final_verification": build_production_landing_final_verification,
    }
    if builders:
        effective_builders.update(builders)

    steps: list[dict[str, Any]] = []
    execution_gate = effective_builders["execution_gate"](env_path=env_path) if env_path else effective_builders["execution_gate"]()
    steps.append(_safe_step_summary("execution_gate", execution_gate))
    steps.append(_safe_step_summary("real_integration_staging_gate", effective_builders["real_integration_staging_gate"]()))
    steps.append(_safe_step_summary("real_integration_gap_register", effective_builders["real_integration_gap_register"]()))
    steps.append(
        _safe_step_summary(
            "real_production_environment_checklist",
            effective_builders["real_production_environment_checklist"](),
        )
    )
    steps.append(_safe_step_summary("business_system_input_packet", effective_builders["business_system_input_packet"]()))
    steps.append(
        _safe_step_summary(
            "business_system_production_readiness",
            effective_builders["business_system_production_readiness"](),
        )
    )
    steps.append(
        _safe_step_summary(
            "business_system_landing_execution_pack",
            effective_builders["business_system_landing_execution_pack"](),
        )
    )
    pilot_signoff = effective_builders["production_pilot_signoff"]()
    steps.append(_safe_step_summary("production_pilot_signoff", pilot_signoff))
    input_kwargs: dict[str, Any] = {
        "closure_evidence": closure_evidence or DEFAULT_CLOSURE_EVIDENCE,
        "pilot_signoff": str(pilot_signoff.get("json_path") or ""),
    }
    steps.append(
        _safe_step_summary(
            "production_landing_input_readiness",
            effective_builders["production_landing_input_readiness"](**input_kwargs),
        )
    )
    steps.append(
        _safe_step_summary(
            "manual_signoff_evidence_ack_status",
            effective_builders["manual_signoff_evidence_ack_status"](),
        )
    )
    steps.append(
        _safe_step_summary(
            "manual_signoff_record_validation",
            effective_builders["manual_signoff_record_validation"](),
        )
    )
    steps.append(
        _safe_step_summary(
            "manual_signoff_record_promote",
            effective_builders["manual_signoff_record_promote"](),
        )
    )
    steps.append(
        _safe_step_summary(
            "production_landing_text_quality",
            effective_builders["production_landing_text_quality"](),
        )
    )
    steps.append(
        _safe_step_summary(
            "operations_console_landing_smoke",
            effective_builders["operations_console_landing_smoke"](),
        )
    )
    steps.append(_safe_step_summary("production_landing_action_pack", effective_builders["production_landing_action_pack"]()))
    steps.append(
        _safe_step_summary(
            "production_landing_blocker_resolution",
            effective_builders["production_landing_blocker_resolution"](),
        )
    )
    final_summary = effective_builders["production_landing_status"]()
    steps.append(_safe_step_summary("production_landing_status", final_summary))
    final_verification = effective_builders["production_landing_final_verification"](
        status_report=str(final_summary.get("json_path") or ""),
    )
    steps.append(_safe_step_summary("production_landing_final_verification", final_verification))

    final_payload = _load_json(str(final_summary.get("json_path") or ""))
    final_blockers = final_payload.get("blockers") if isinstance(final_payload.get("blockers"), list) else []
    blocked_steps = [item["step_id"] for item in steps if item.get("status") in {"blocked", "failed"}]
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    final_status = str(final_summary.get("status") or "skipped")
    status = "blocked" if blocked_steps else final_status
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.4",
        "phase": "v4.7 Production Landing Sequential Refresh",
        "status": status,
        "final_status": final_status,
        "mode": "read_only_sequential_refresh",
        "read_only": True,
        "steps": steps,
        "step_count": len(steps),
        "blocked_steps": blocked_steps,
        "final_status_json_path": str(final_summary.get("json_path") or ""),
        "final_blockers": [str(item) for item in final_blockers],
        "blocker_count": len(final_blockers),
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_refresh_status"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "final_status": final_status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "step_count": len(steps),
        "blocked_step_count": len(blocked_steps),
        "blocker_count": len(final_blockers),
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh production landing status reports in dependency order.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-path", default=None)
    parser.add_argument("--closure-evidence", default=str(DEFAULT_CLOSURE_EVIDENCE))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_refresh_status(
        output_dir=args.output_dir,
        env_path=args.env_path,
        closure_evidence=args.closure_evidence,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
