from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.production_landing_env_check import (
    DEFAULT_ENV_PATH,
    REQUIRED_ENV_BY_DOMAIN,
    build_production_landing_env_check,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_execution_gate"
STAGING_DOMAINS = ["real_llm", "postgres", "redis", "external_mcp"]
BUSINESS_DOMAIN = "business_system"
DOMAIN_IDS = [*STAGING_DOMAINS, BUSINESS_DOMAIN]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_domains(value: str | list[str] | None) -> list[str]:
    if value is None:
        return DOMAIN_IDS
    if isinstance(value, list):
        requested = value
    else:
        requested = [item.strip() for item in value.split(",")]
    domains: list[str] = []
    for item in requested:
        if not item:
            continue
        if item not in DOMAIN_IDS:
            raise ValueError(f"unsupported domain: {item}")
        if item not in domains:
            domains.append(item)
    return domains or DOMAIN_IDS


def _domain_map(env_check_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    domains = env_check_payload.get("domains") if isinstance(env_check_payload.get("domains"), list) else []
    return {str(item.get("domain_id")): item for item in domains if isinstance(item, dict)}


def _safe_domain_summary(domain: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_id": str(domain.get("domain_id") or ""),
        "ready_for_execute": bool(domain.get("ready_for_execute", False)),
        "blocker_reason": str(domain.get("blocker_reason") or ""),
        "next_action": str(domain.get("next_action") or ""),
        "command_after_fill": str(domain.get("command_after_fill") or ""),
        "required_env_keys": [str(item) for item in domain.get("required_env_keys", []) if isinstance(item, str)][:24],
        "missing_keys": [str(item) for item in domain.get("missing_keys", []) if isinstance(item, str)][:16],
        "placeholder_keys": [str(item) for item in domain.get("placeholder_keys", []) if isinstance(item, str)][:16],
        "mismatch_keys": [str(item) for item in domain.get("mismatch_keys", []) if isinstance(item, str)][:16],
    }


def _runner_commands(*, requested_domains: list[str], ready_domains: list[str]) -> list[str]:
    commands = ["python scripts/production_landing_env_runner.py --action env-check"]
    if "real_llm" in requested_domains and "real_llm" not in ready_domains:
        commands.append("python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight")
        commands.append("python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check")
        commands.append("powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1")
    if all(item in ready_domains for item in ["postgres", "redis", "external_mcp"]):
        commands.append("python scripts/production_landing_env_runner.py --action local-infra-mcp-smoke")
    elif "postgres" in ready_domains and "redis" in ready_domains:
        commands.append("python scripts/production_landing_env_runner.py --action local-infra-smoke")
    if "business_system" in ready_domains:
        commands.append("python scripts/production_landing_env_runner.py --action local-business-smoke")
    requested_staging = [item for item in requested_domains if item in STAGING_DOMAINS]
    if requested_staging and all(item in ready_domains for item in requested_staging):
        commands.append("python scripts/production_landing_env_runner.py --action staging-smoke")
    if BUSINESS_DOMAIN in requested_domains and BUSINESS_DOMAIN in ready_domains:
        commands.append("python scripts/production_landing_env_runner.py --action business-smoke")
    return commands


def build_production_landing_execution_gate(
    *,
    env_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    domains: str | list[str] | None = None,
) -> dict[str, Any]:
    requested_domains = _parse_domains(domains)
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    env_summary = build_production_landing_env_check(
        env_path=env_path or DEFAULT_ENV_PATH,
        allow_real_llm_evidence_override=True,
    )
    env_payload = _load_json(env_summary.get("json_path", ""))
    by_domain = _domain_map(env_payload)

    selected_domains = [_safe_domain_summary(by_domain.get(domain_id, {"domain_id": domain_id})) for domain_id in requested_domains]
    ready_domains = [item["domain_id"] for item in selected_domains if item["ready_for_execute"]]
    blocked_domains = [item["domain_id"] for item in selected_domains if not item["ready_for_execute"]]
    all_ready = len(ready_domains) == len(selected_domains)
    env_file_present = bool(env_payload.get("env_file_present", False))

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.6.4",
        "phase": "v4.6 Production Landing Execution Gate",
        "status": "success" if all_ready else ("partial" if env_file_present else "skipped"),
        "mode": "read_only_execution_gate",
        "read_only": True,
        "env_path": str(Path(env_path) if env_path else DEFAULT_ENV_PATH),
        "env_file_present": env_file_present,
        "requested_domains": requested_domains,
        "requested_domain_count": len(requested_domains),
        "ready_domains": ready_domains,
        "ready_domain_count": len(ready_domains),
        "blocked_domains": blocked_domains,
        "blocked_domain_count": len(blocked_domains),
        "all_requested_domains_ready_for_execute": all_ready,
        "execution_allowed": all_ready,
        "real_smoke_executed": False,
        "business_smoke_executed": False,
        "domains": selected_domains,
        "safe_runner_commands": _runner_commands(requested_domains=requested_domains, ready_domains=ready_domains),
        "required_env_by_domain": {domain_id: REQUIRED_ENV_BY_DOMAIN[domain_id] for domain_id in requested_domains},
        "env_check_json_path": str(env_summary.get("json_path", "")),
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_execution_gate"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "requested_domain_count": len(requested_domains),
        "ready_domain_count": len(ready_domains),
        "blocked_domain_count": len(blocked_domains),
        "execution_allowed": all_ready,
        "secret_plaintext_output": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing execution gate",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execution_allowed: {payload.get('execution_allowed', False)}",
        f"- ready_domain_count: {payload.get('ready_domain_count', 0)}/{payload.get('requested_domain_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Domains",
    ]
    for item in payload.get("domains", []):
        lines.append(
            f"- {item.get('domain_id')}: ready={item.get('ready_for_execute')} "
            f"blocker={item.get('blocker_reason') or '-'} next_action={item.get('next_action') or '-'}"
        )
    lines.extend(["", "## Safe runner commands"])
    for command in payload.get("safe_runner_commands", []):
        lines.append(f"- `{command}`")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only production landing execution gate.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--domains", default=",".join(DOMAIN_IDS))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_execution_gate(
        env_path=args.env_path,
        output_dir=args.output_dir,
        domains=args.domains,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
