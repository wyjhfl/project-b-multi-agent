from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "governance_policy"


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


def _build_policy_items() -> list[dict[str, Any]]:
    return [
        {
            "policy": "default_mode",
            "status": "enforced",
            "summary": "default fake/offline path is preserved",
            "boundary": "no real external LLM execution in default flow",
            "evidence_paths": [
                "docs/v3_3_operational_automation_governance_plan.md",
                "README.md",
                "AGENTS.md",
            ],
        },
        {
            "policy": "ci_test_llm_boundary",
            "status": "enforced",
            "summary": "default pytest/CI path does not call real LLM",
            "boundary": "real provider tests are opt-in and skipped by default",
            "evidence_paths": [
                "README.md",
                "AGENTS.md",
                "docs/production_readiness_checklist.md",
            ],
        },
        {
            "policy": "real_llm_opt_in",
            "status": "enforced",
            "summary": "real LLM execution is opt-in only",
            "boundary": "missing required env must be recorded as skipped",
            "evidence_paths": [
                "docs/real_llm_optional_retry_log_v32.md",
                "docs/real_llm_pilot_execution_log_v31.md",
                "scripts/real_llm_smoke.ps1",
            ],
        },
        {
            "policy": "secret_handling",
            "status": "enforced",
            "summary": "do not commit API key/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL plaintext",
            "boundary": "docs and scripts only use placeholders or redacted output",
            "evidence_paths": [
                ".env.example",
                ".env.production.example",
                "docs/production_readiness_checklist.md",
            ],
        },
        {
            "policy": "audit_export_redaction",
            "status": "enforced",
            "summary": "audit export follows whitelist and redaction requirement",
            "boundary": "no raw prompt or secret plaintext in export path",
            "evidence_paths": [
                "docs/failure_diagnostics_pack_v32.md",
                "docs/operations_troubleshooting_index_v31.md",
                "app/api/audit.py",
            ],
        },
        {
            "policy": "oidc_minimal_drill",
            "status": "enforced",
            "summary": "OIDC is minimal IdP drill boundary, not production-grade SSO completion",
            "boundary": "no production SSO completion claim",
            "evidence_paths": [
                "docs/oidc_minimal_idp_drill_v31.md",
                "docs/production_readiness_checklist.md",
                "app/core/deployment_guard.py",
            ],
        },
        {
            "policy": "report_index_retention",
            "status": "enforced",
            "summary": "report index and retention are read-only",
            "boundary": "list stale candidates only, no automatic deletion",
            "evidence_paths": [
                "scripts/report_index.py",
                "docs/report_index_retention_runbook_v33.md",
                "tests/test_report_index_v331.py",
            ],
        },
        {
            "policy": "config_drift_checklist",
            "status": "enforced",
            "summary": "config drift checks are read-only",
            "boundary": "no auto-fix, no env mutation",
            "evidence_paths": [
                "scripts/config_drift_check.py",
                "docs/config_drift_checklist_v33.md",
                "tests/test_config_drift_v332.py",
            ],
        },
        {
            "policy": "release_tag_boundary",
            "status": "enforced",
            "summary": "historical tags are immutable and release creation is manual",
            "boundary": "release-created state must be recorded by follow-up documentation",
            "evidence_paths": [
                "docs/post_release_check_v3.2.0.md",
                "docs/post_release_check_v3.1.0.md",
                "README.md",
            ],
        },
        {
            "policy": "non_claim_boundary",
            "status": "enforced",
            "summary": "documentation does not claim public-prod direct launch or full completion of optional capabilities",
            "boundary": "no claims for real LLM production acceptance, production-grade SSO/OIDC, multitenancy, or complex BI full delivery",
            "evidence_paths": [
                "README.md",
                "AGENTS.md",
                "docs/production_readiness_checklist.md",
            ],
        },
    ]


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Governance Policy Summary v3.3 (Read Only)",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        "",
        "## Scope",
        "- Governance entry for security, release, opt-in real LLM, OIDC, reporting, and retention boundaries.",
        "- Read-only summary for operations handoff and internal pilot governance.",
        "",
        "## Policy Status",
    ]
    for item in payload.get("policy_items", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {item.get('policy', 'unknown')}",
                f"- status: {item.get('status', 'unknown')}",
                f"- summary: {item.get('summary', '')}",
                f"- boundary: {item.get('boundary', '')}",
                f"- evidence_paths: {json.dumps(item.get('evidence_paths', []), ensure_ascii=False)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Boundary Declarations",
            "- default fake/offline",
            "- default pytest/CI no real LLM",
            "- real LLM opt-in only; missing env => skipped",
            "- no secret plaintext commit",
            "- release/tag boundary preserved",
            "",
        ]
    )
    return "\n".join(lines)


def build_governance_policy_summary(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "scope": "v3.3 governance policy summary for operations and pilot handoff",
        "read_only": True,
        "real_llm_executed": False,
        "policy_items": _build_policy_items(),
        "boundary_declarations": [
            "default fake/offline",
            "default pytest/CI no real LLM",
            "real LLM opt-in only; missing env => skipped",
            "no secret plaintext commit",
            "audit export redaction boundary preserved",
            "OIDC minimal drill boundary preserved",
            "report retention read-only boundary preserved",
            "config drift read-only boundary preserved",
            "history tag immutability boundary preserved",
            "manual release then documentation closure",
            "no public production direct launch claim",
            "no claim for real LLM production acceptance completion",
            "no claim for production-grade SSO/OIDC completion",
            "no claim for multitenancy or complex BI full completion",
        ],
        "evidence_index": {
            "plan_path": "docs/v3_3_operational_automation_governance_plan.md",
            "policy_doc_path": "docs/governance_policy_summary_v33.md",
            "report_index_runbook_path": "docs/report_index_retention_runbook_v33.md",
            "config_drift_runbook_path": "docs/config_drift_checklist_v33.md",
        },
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_governance_policy_summary"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": "ok",
        "json_path": _to_rel(json_path),
        "markdown_path": _to_rel(md_path),
        "policy_count": len(payload["policy_items"]),
        "read_only": True,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only governance policy summary (JSON + Markdown)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_governance_policy_summary(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
