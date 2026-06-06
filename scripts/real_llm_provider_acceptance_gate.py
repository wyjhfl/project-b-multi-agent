from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_llm_provider_acceptance_gate"
DEFAULT_PILOT_REPORT_DIR = ROOT_DIR / "docs" / "reports" / "real_llm_pilot"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

REAL_LLM_OPT_IN_KEYS = [
    "REAL_LLM_SMOKE_ENABLED",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_PREFLIGHT_ENABLED",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
]

REAL_LLM_CONFIG_KEYS = [
    "REAL_LLM_PROVIDER",
    "REAL_LLM_MODEL",
    "REAL_LLM_BASE_URL",
    "REAL_LLM_API_KEY_ENV",
    "REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS",
]

BOUNDARY_DECLARATIONS = [
    "只读 Real LLM provider acceptance gate",
    "仅检查 opt-in 配置、本地测试覆盖和可选 pilot report 文件元数据",
    "不调用真实外网 LLM",
    "不执行 provider network check",
    "不读取或输出真实 API key、token、client_secret 或连接串密码原文",
    "不读取 pilot report 正文",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不把 opt-in smoke、fallback 或只读门禁宣称为生产验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_presence(keys: list[str]) -> dict[str, dict[str, Any]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _target_env_presence(env_name_key: str) -> dict[str, Any]:
    env_name = (os.getenv(env_name_key, "") or "").strip()
    return {
        "env_name_key": env_name_key,
        "env_name": env_name,
        "present": bool(env_name and os.getenv(env_name)),
    }


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _local_checks() -> dict[str, dict[str, Any]]:
    paths = {
        "preflight_module": "app/harness/llm/preflight.py",
        "provider_module": "app/agent/nl2sql/provider.py",
        "budget_module": "app/harness/llm/budget.py",
        "cache_module": "app/harness/llm/cache.py",
        "pilot_report_module": "app/harness/llm/pilot_report.py",
        "pilot_smoke_report_module": "app/harness/llm/pilot_smoke_report.py",
        "real_llm_smoke_script": "scripts/real_llm_smoke.ps1",
        "preflight_tests": "tests/test_llm_preflight_v51.py",
        "real_smoke_tests": "tests/test_real_llm_smoke_v52.py",
        "real_judge_tests": "tests/test_real_llm_judge_smoke_v54.py",
        "budget_cache_tests": "tests/test_llm_budget_cache_v45.py",
        "guardrail_tests": "tests/test_guardrails_pii_leak_v44.py",
        "pilot_report_tests": "tests/test_real_llm_pilot_report_v91.py",
    }
    return {key: {"path": path, "present": _path_exists(path)} for key, path in paths.items()}


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _pilot_report_index(pilot_report_dir: str | Path | None) -> dict[str, Any]:
    path = Path(pilot_report_dir) if pilot_report_dir else DEFAULT_PILOT_REPORT_DIR
    if not path.exists():
        return {
            "provided_path": str(path),
            "exists": False,
            "status": "skipped",
            "missing_conditions": ["pilot_report_dir:not_found"],
            "files": [],
            "file_count": 0,
            "content_read": False,
        }
    if not path.is_dir():
        return {
            "provided_path": str(path),
            "exists": True,
            "status": "skipped",
            "missing_conditions": ["pilot_report_dir:not_directory"],
            "files": [],
            "file_count": 0,
            "content_read": False,
        }
    files: list[dict[str, Any]] = []
    for item in sorted(path.glob("*")):
        if not item.is_file() or item.suffix.lower() not in {".json", ".md"}:
            continue
        files.append(
            {
                "name": item.name,
                "suffix": item.suffix.lower(),
                "size_bytes": item.stat().st_size,
                "modified_utc": datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return {
        "provided_path": str(path),
        "exists": True,
        "status": "partial" if files else "skipped",
        "missing_conditions": [] if files else ["pilot_report_dir:no_json_or_markdown_reports"],
        "files": files[-20:],
        "file_count": len(files),
        "content_read": False,
    }


def _acceptance_checks(local: dict[str, dict[str, Any]], evidence_index: dict[str, Any]) -> list[dict[str, Any]]:
    opt_in_missing = [f"opt_in:{key}_not_enabled" for key in REAL_LLM_OPT_IN_KEYS if not _env_enabled(key)]
    env = _env_presence(REAL_LLM_CONFIG_KEYS)
    api_target = _target_env_presence("REAL_LLM_API_KEY_ENV")
    provider = (os.getenv("REAL_LLM_PROVIDER", "") or "").strip().lower()
    model_present = bool(os.getenv("REAL_LLM_MODEL"))
    timeout_present = bool(os.getenv("REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS"))

    return [
        {
            "check_id": "preflight_config",
            "status": "partial" if not opt_in_missing and model_present and api_target["present"] else "skipped",
            "missing_conditions": sorted(set(opt_in_missing + ([] if model_present else ["env:REAL_LLM_MODEL"]) + ([] if api_target["present"] else ["env_target:REAL_LLM_API_KEY_ENV_target_missing"]))),
            "evidence": {
                "env": env,
                "api_key_target": api_target,
                "provider_supported": provider in {"", "litellm"},
                "network_check_executed": False,
            },
        },
        {
            "check_id": "network_check_gate",
            "status": "partial" if _env_enabled("REAL_LLM_PREFLIGHT_NETWORK_CHECK") else "skipped",
            "missing_conditions": [] if _env_enabled("REAL_LLM_PREFLIGHT_NETWORK_CHECK") else ["opt_in:REAL_LLM_PREFLIGHT_NETWORK_CHECK_not_enabled"],
            "evidence": {"network_check_executed": False, "timeout_configured": timeout_present},
        },
        {
            "check_id": "smoke_opt_in",
            "status": "partial" if not opt_in_missing else "skipped",
            "missing_conditions": opt_in_missing,
            "evidence": {
                "real_llm_smoke_script_present": local["real_llm_smoke_script"]["present"],
                "real_smoke_tests_present": local["real_smoke_tests"]["present"],
                "real_judge_tests_present": local["real_judge_tests"]["present"],
                "real_llm_executed": False,
            },
        },
        {
            "check_id": "budget_cache_fallback",
            "status": "partial" if local["budget_module"]["present"] and local["cache_module"]["present"] and local["budget_cache_tests"]["present"] else "skipped",
            "missing_conditions": [key for key in ("budget_module", "cache_module", "budget_cache_tests") if not local[key]["present"]],
            "evidence": {"budget_cache_tests_present": local["budget_cache_tests"]["present"]},
        },
        {
            "check_id": "pii_prompt_guardrails",
            "status": "partial" if local["guardrail_tests"]["present"] else "skipped",
            "missing_conditions": [] if local["guardrail_tests"]["present"] else ["local:guardrail_tests"],
            "evidence": {"guardrail_tests_present": local["guardrail_tests"]["present"]},
        },
        {
            "check_id": "report_redaction",
            "status": "partial" if local["pilot_report_module"]["present"] and local["pilot_report_tests"]["present"] else "skipped",
            "missing_conditions": [key for key in ("pilot_report_module", "pilot_report_tests") if not local[key]["present"]],
            "evidence": {"pilot_report_content_read": False, "pilot_report_tests_present": local["pilot_report_tests"]["present"]},
        },
        {
            "check_id": "judge_acceptance",
            "status": "partial" if local["real_judge_tests"]["present"] else "skipped",
            "missing_conditions": [] if local["real_judge_tests"]["present"] else ["local:real_judge_tests"],
            "evidence": {"judge_smoke_tests_present": local["real_judge_tests"]["present"], "real_llm_executed": False},
        },
        {
            "check_id": "evidence_index",
            "status": evidence_index["status"],
            "missing_conditions": evidence_index["missing_conditions"],
            "evidence": {
                "pilot_report_dir_exists": evidence_index["exists"],
                "file_count": evidence_index["file_count"],
                "content_read": evidence_index["content_read"],
            },
        },
    ]


def _derive_status(checks: list[dict[str, Any]], local: dict[str, dict[str, Any]], evidence_index: dict[str, Any]) -> str:
    if any(not item["present"] for item in local.values()):
        return "skipped"
    if any(check["status"] == "blocked" for check in checks):
        return "blocked"
    if any(check["status"] == "skipped" for check in checks):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.7 Real LLM provider acceptance gate（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        f"- provider_network_check_executed: {payload.get('provider_network_check_executed', False)}",
        "",
        "## 门禁项",
    ]
    for check in payload.get("acceptance_checks", []):
        lines.extend(
            [
                f"### {check['check_id']}",
                f"- status: {check['status']}",
                f"- missing_conditions: {json.dumps(check.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_llm_provider_acceptance_gate(
    *,
    output_dir: str | Path | None = None,
    pilot_report_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    local = _local_checks()
    evidence_index = _pilot_report_index(pilot_report_dir)
    checks = _acceptance_checks(local, evidence_index)
    missing_conditions = sorted({item for check in checks for item in check.get("missing_conditions", [])})
    status = _derive_status(checks, local, evidence_index)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.7.0",
        "phase": "v3.7 Phase 17.3",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "provider_network_check_executed": False,
        "pilot_report_content_read": False,
        "secret_plaintext_output": False,
        "prompt_plaintext_output": False,
        "env": _env_presence(REAL_LLM_OPT_IN_KEYS + REAL_LLM_CONFIG_KEYS),
        "api_key_target": _target_env_presence("REAL_LLM_API_KEY_ENV"),
        "local_checks": local,
        "pilot_report_index": evidence_index,
        "acceptance_checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "真实 LLM opt-in 演练前必须补齐 REAL_LLM_* 开关、模型和 API key env target。",
            "真实 smoke 报告必须包含 request_id、tokens、cost、fallback、budget、cache 和审计证据。",
            "Phase 17.4 可继续推进 Store and Redis production readiness drill。",
        ],
        "output_dir": str(output_root),
    }
    if _contains_secret_like_text(json.dumps(payload, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_llm_provider_acceptance_gate"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "provider_network_check_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "check_count": len(checks),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.7 Real LLM provider acceptance gate（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--pilot-report-dir", default=str(DEFAULT_PILOT_REPORT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_real_llm_provider_acceptance_gate(
        output_dir=args.output_dir,
        pilot_report_dir=args.pilot_report_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
