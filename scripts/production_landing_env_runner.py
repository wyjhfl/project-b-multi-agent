from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / "local" / "production_landing.staging.env"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_env_runner"

ALLOWED_ACTIONS = {
    "env-check": ["scripts/production_landing_env_check.py"],
    "xiaomi-llm-preflight": [
        "scripts/production_landing_xiaomi_llm_preflight_runner.py",
        "--execute-network-check",
    ],
    "staging-smoke": ["scripts/real_integration_staging_smoke.py", "--execute", "--domains", "real_llm,postgres,redis,external_mcp"],
    "local-infra-smoke": ["scripts/real_integration_staging_smoke.py", "--execute", "--domains", "postgres,redis"],
    "local-infra-mcp-smoke": ["scripts/real_integration_staging_smoke.py", "--execute", "--domains", "postgres,redis,external_mcp"],
    "business-smoke": ["scripts/business_system_read_smoke.py", "--execute"],
    "local-business-smoke": ["scripts/production_landing_local_business_smoke.py"],
}
BUSINESS_OWNER_ENV = {
    "business_owner": "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "security_reviewer": "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "operations_owner": "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "data_owner": "BUSINESS_SYSTEM_DATA_OWNER",
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(token|api[_-]?key|password|client[_-]?secret|jwt[_-]?secret)\s*[:=]\s*([^\s,]+)"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_TEXT_PATTERNS:
        redacted = pattern.sub("[redacted-secret-like-text]", redacted)
    return redacted


def _safe_lines(text: str, limit: int = 80) -> list[str]:
    return [_redact_text(line) for line in text.splitlines()[:limit]]


def _business_owner_values(
    *,
    business_owner: str = "",
    security_reviewer: str = "",
    operations_owner: str = "",
    data_owner: str = "",
) -> dict[str, str]:
    return {
        "BUSINESS_SYSTEM_BUSINESS_OWNER": business_owner.strip(),
        "BUSINESS_SYSTEM_SECURITY_REVIEWER": security_reviewer.strip(),
        "BUSINESS_SYSTEM_OPERATIONS_OWNER": operations_owner.strip(),
        "BUSINESS_SYSTEM_DATA_OWNER": data_owner.strip(),
    }


def _inject_business_owner_env(env: dict[str, str], owner_values: dict[str, str]) -> dict[str, bool]:
    present: dict[str, bool] = {}
    for env_key in BUSINESS_OWNER_ENV.values():
        value = owner_values.get(env_key, "").strip()
        if value:
            env[env_key] = value
        present[env_key] = bool((env.get(env_key, "") or "").strip())
    return present


def _extract_child_status(stdout: str, return_code: int) -> tuple[str, dict[str, Any]]:
    decoder = json.JSONDecoder()
    payload: Any = None
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(stdout[index:])
        except Exception:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        return ("success" if return_code == 0 else "failed"), {}
    if not isinstance(payload, dict):
        return ("success" if return_code == 0 else "failed"), {}
    status = str(payload.get("status") or ("success" if return_code == 0 else "failed"))
    if status not in {"success", "partial", "skipped", "blocked", "failed"}:
        status = "success" if return_code == 0 else "failed"
    if return_code != 0 and status in {"success", "partial", "skipped"}:
        status = "failed"
    return status, payload


def _child_domain_counts(child_summary: dict[str, Any]) -> tuple[int, int]:
    ready = child_summary.get("ready_domain_count")
    total = child_summary.get("domain_count")
    if isinstance(ready, int) and isinstance(total, int) and total:
        return ready, total
    domains = child_summary.get("domains")
    if isinstance(domains, list):
        domain_items = [item for item in domains if isinstance(item, dict)]
        success_count = sum(1 for item in domain_items if item.get("status") == "success")
        return success_count, len(domain_items)
    if child_summary.get("status") == "success" and isinstance(total, int) and total:
        return total, total
    return 0, int(total or 0) if isinstance(total, int) else 0


def _child_xiaomi_preflight_summary(child_summary: dict[str, Any]) -> dict[str, Any]:
    preflight = child_summary.get("preflight")
    preflight_payload = preflight if isinstance(preflight, dict) else {}
    blockers = child_summary.get("acceptance_blockers")
    return {
        "api_key_present": bool(child_summary.get("api_key_present", preflight_payload.get("api_key_present", False))),
        "network_check_requested": bool(
            child_summary.get("execute_network_check", preflight_payload.get("network_check_requested", False))
        ),
        "network_check_allowed": bool(preflight_payload.get("network_check_allowed", False)),
        "network_check_executed": bool(preflight_payload.get("network_check_executed", False)),
        "real_llm_executed": bool(child_summary.get("real_llm_executed", False)),
        "safe_next_action": str(child_summary.get("safe_next_action") or ""),
        "acceptance_blockers": [str(item) for item in blockers] if isinstance(blockers, list) else [],
    }


def _load_child_json_payload(child_summary: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(child_summary.get("json_path") or "").strip()
    if not raw_path:
        return child_summary
    try:
        path = Path(raw_path).resolve()
        root = ROOT_DIR.resolve()
        if not str(path).startswith(str(root)) or not path.is_file():
            return child_summary
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return child_summary
    return loaded if isinstance(loaded, dict) else child_summary


def build_production_landing_env_runner(
    *,
    action: str,
    env_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    timeout_seconds: int = 120,
    business_owner: str = "",
    security_reviewer: str = "",
    operations_owner: str = "",
    data_owner: str = "",
) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    env_values = _parse_env_file(path)
    action_args = [*ALLOWED_ACTIONS[action]]
    if action == "env-check":
        action_args.extend(
            [
                "--env-path",
                str(path),
                "--output-dir",
                str(output_root / "child_env_check"),
                "--xiaomi-preflight-report-dir",
                str(output_root / "child_xiaomi_llm_preflight"),
            ]
        )
    elif action == "xiaomi-llm-preflight":
        action_args.extend(["--output-dir", "docs/reports/production_landing_xiaomi_llm_preflight"])
    env = {**os.environ, **env_values}
    owner_env_present = _inject_business_owner_env(
        env,
        _business_owner_values(
            business_owner=business_owner,
            security_reviewer=security_reviewer,
            operations_owner=operations_owner,
            data_owner=data_owner,
        ),
    )
    if action == "business-smoke":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts\\business_system_read_smoke.ps1",
            "-UseExistingEnv",
            "-EnvPath",
            str(path),
        ]
        display_command = (
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 "
            "-UseExistingEnv -EnvPath <local-env-path>"
        )
    else:
        command = [sys.executable, *action_args]
        display_command = "python " + " ".join(action_args)
    result = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_lines = _safe_lines(result.stdout)
    stderr_lines = _safe_lines(result.stderr)
    child_status, child_summary = _extract_child_status(result.stdout, result.returncode)
    child_detail = _load_child_json_payload(child_summary) if action == "xiaomi-llm-preflight" else child_summary
    child_ready_count, child_domain_count = _child_domain_counts(child_summary)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.6.1",
        "phase": "v4.6 Production Landing Env Runner",
        "status": child_status,
        "mode": "controlled_env_runner",
        "action": action,
        "env_path": str(path),
        "env_file_present": path.exists(),
        "env_key_count": len(env_values),
        "command": display_command,
        "return_code": result.returncode,
        "child_status": child_status,
        "child_summary": {
            "status": str(child_summary.get("status") or ""),
            "ready_domain_count": child_ready_count,
            "domain_count": child_domain_count,
            "secret_plaintext_output": bool(child_summary.get("secret_plaintext_output", False)),
        },
        "child_xiaomi_preflight": _child_xiaomi_preflight_summary(child_detail) if action == "xiaomi-llm-preflight" else {},
        "business_owner_env_present": owner_env_present if action == "business-smoke" else {},
        "stdout": stdout_lines,
        "stderr": stderr_lines,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_env_runner"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "action": action,
        "return_code": result.returncode,
        "secret_plaintext_output": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing env runner",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- action: {payload.get('action', '')}",
        f"- return_code: {payload.get('return_code', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Stdout",
    ]
    lines.extend(f"- {line}" for line in payload.get("stdout", [])[:20])
    lines.extend(["", "## Stderr"])
    lines.extend(f"- {line}" for line in payload.get("stderr", [])[:20])
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled production landing commands with local env file.")
    parser.add_argument("--action", choices=sorted(ALLOWED_ACTIONS), required=True)
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--business-owner", default="")
    parser.add_argument("--security-reviewer", default="")
    parser.add_argument("--operations-owner", default="")
    parser.add_argument("--data-owner", default="")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_env_runner(
        action=args.action,
        env_path=args.env_path,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
        business_owner=args.business_owner,
        security_reviewer=args.security_reviewer,
        operations_owner=args.operations_owner,
        data_owner=args.data_owner,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
