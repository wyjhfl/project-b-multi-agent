from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_staging_gate"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}

CONTROLLED_EXECUTION_FLAGS = [
    "real_llm_executed",
    "database_connected",
    "redis_connected",
    "external_mcp_connected",
    "migration_executed",
    "business_data_written",
    "audit_data_written",
    "metrics_data_written",
]

OPTIONAL_BLOCKING_FLAGS = [
    "provider_network_check_executed",
    "mcp_process_started",
    "mcp_tools_list_executed",
    "mcp_tools_call_executed",
    "business_system_connected",
    "secret_plaintext_output",
    "prompt_plaintext_output",
]

ALLOWED_CONTROLLED_TRUE_FLAGS = {
    "real_integration_staging_smoke": {
        "real_llm_executed",
        "database_connected",
        "redis_connected",
        "external_mcp_connected",
    },
    "production_migration_drill": {"database_connected", "migration_executed"},
}

BOUNDARY_DECLARATIONS = [
    "只读组合真实集成 staging gate。",
    "仅消费既有证据目录中的 JSON 结构字段，不读取 Markdown 正文，不连接真实外部服务。",
    "不调用真实 LLM，不连接真实 PostgreSQL/Redis/MCP，不执行 migration，不写业务/审计/指标数据。",
    "发现缺失证据时标记 skipped，不伪造成 success。",
    "发现 secret-like 内容或异常执行 flag 时标记 blocked，且不输出原文。",
    "Go/No-Go 仅提供受控人工复核入口，public_production_direct_launch 始终 No-Go。",
]

DEFAULT_EVIDENCE_DIRS = {
    "real_integration_env_profile": ROOT_DIR / "docs" / "reports" / "real_integration_env_profile",
    "real_integration_smoke_plan": ROOT_DIR / "docs" / "reports" / "real_integration_smoke_plan",
    "real_integration_staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "real_integration_readiness": ROOT_DIR / "docs" / "reports" / "real_integration_readiness",
    "real_llm_provider_acceptance_gate": ROOT_DIR / "docs" / "reports" / "real_llm_provider_acceptance_gate",
    "external_mcp_acceptance_gate": ROOT_DIR / "docs" / "reports" / "external_mcp_acceptance_gate",
    "store_redis_readiness_drill": ROOT_DIR / "docs" / "reports" / "store_redis_readiness_drill",
    "production_migration_drill": ROOT_DIR / "docs" / "reports" / "production_migration_drill",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip(" \"'<>[]{}\\")
                if candidate.lower() in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _safe_path_text(path: Path | str | None) -> str | None:
    if path is None:
        return None
    text = str(path)
    return "[redacted-secret-like-path]" if _contains_secret_like_text(text) else text


def _iter_leaf_strings(value: Any) -> list[str]:
    results: list[str] = []
    if isinstance(value, str):
        results.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            results.extend(_iter_leaf_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            results.extend(_iter_leaf_strings(nested))
    return results


def _extract_true_flags(payload: dict[str, Any], flag_names: list[str]) -> list[str]:
    return [flag for flag in flag_names if payload.get(flag) is True]


def _safe_count(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _find_latest_json_file(directory: Path) -> Path | None:
    json_files = [item for item in directory.glob("*.json") if item.is_file()]
    if not json_files:
        return None
    return max(json_files, key=_json_report_sort_key)


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = _read_json_payload(path)
        generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _rank_evidence_payload(evidence_id: str, payload: dict[str, Any]) -> tuple[int, int, str]:
    source_status = str(payload.get("status", "")).strip().lower()
    controlled_flags = ALLOWED_CONTROLLED_TRUE_FLAGS.get(evidence_id, set())
    controlled_true_count = sum(1 for flag in controlled_flags if payload.get(flag) is True)
    if source_status == "success" and controlled_true_count:
        return (4, controlled_true_count, source_status)
    if source_status == "success":
        return (3, controlled_true_count, source_status)
    if source_status == "partial":
        return (2, controlled_true_count, source_status)
    if source_status == "blocked":
        return (1, controlled_true_count, source_status)
    return (0, controlled_true_count, source_status)


def _select_evidence_json_file(evidence_id: str, directory: Path) -> tuple[Path, dict[str, Any]] | None:
    candidates: list[tuple[tuple[int, int, str], str, float, str, Path, dict[str, Any]]] = []
    for item in directory.glob("*.json"):
        if not item.is_file():
            continue
        try:
            payload = _read_json_payload(item)
        except Exception:
            continue
        candidates.append(
            (
                _rank_evidence_payload(evidence_id, payload),
                str(payload.get("generated_at") or ""),
                item.stat().st_mtime,
                item.name,
                item,
                payload,
            )
        )
    if not candidates:
        return None
    _, _, _, _, path, payload = max(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))
    return path, payload


def _read_json_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence_json_not_object")
    return data


def _sanitize_payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": payload.get("generated_at"),
        "phase": payload.get("phase"),
        "version": payload.get("version"),
        "status": payload.get("status"),
        "read_only": payload.get("read_only"),
        "secret_plaintext_output": payload.get("secret_plaintext_output"),
        "prompt_plaintext_output": payload.get("prompt_plaintext_output"),
        "check_count": _safe_count(payload.get("check_count")),
        "component_count": _safe_count(payload.get("component_count")),
        "integration_count": _safe_count(payload.get("integration_count")),
        "missing_condition_count": len(payload.get("missing_conditions", [])) if isinstance(payload.get("missing_conditions"), list) else None,
        "real_llm_executed": payload.get("real_llm_executed") is True,
        "database_connected": payload.get("database_connected") is True,
        "redis_connected": payload.get("redis_connected") is True,
        "external_mcp_connected": payload.get("external_mcp_connected") is True,
        "migration_executed": payload.get("migration_executed") is True,
    }


def _index_evidence(evidence_id: str, directory: Path) -> dict[str, Any]:
    if not directory.exists():
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "directory": _safe_path_text(directory),
            "latest_json_path": None,
            "latest_json_present": False,
            "content_read": False,
            "missing_conditions": [f"evidence_dir:{evidence_id}:not_found"],
            "blocking_reasons": [],
            "warnings": [],
            "safe_summary": {},
        }
    if not directory.is_dir():
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "directory": _safe_path_text(directory),
            "latest_json_path": None,
            "latest_json_present": False,
            "content_read": False,
            "missing_conditions": [f"evidence_dir:{evidence_id}:not_directory"],
            "blocking_reasons": [],
            "warnings": [],
            "safe_summary": {},
        }

    selected = _select_evidence_json_file(evidence_id, directory)
    if selected is None:
        latest_json = _find_latest_json_file(directory)
        if latest_json is not None:
            return {
                "evidence_id": evidence_id,
                "status": "blocked",
                "directory": _safe_path_text(directory),
                "latest_json_path": _safe_path_text(latest_json),
                "latest_json_present": True,
                "content_read": True,
                "missing_conditions": [],
                "blocking_reasons": ["evidence_json_invalid"],
                "warnings": [],
                "safe_summary": {},
            }
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "directory": _safe_path_text(directory),
            "latest_json_path": None,
            "latest_json_present": False,
            "content_read": False,
            "missing_conditions": [f"evidence_dir:{evidence_id}:no_json_evidence"],
            "blocking_reasons": [],
            "warnings": [],
            "safe_summary": {},
        }
    latest_json, payload = selected

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if any(_contains_secret_like_text(text) for text in _iter_leaf_strings(payload)):
        blocking_reasons.append("secret_like_content_detected")

    true_execution_flags = _extract_true_flags(payload, CONTROLLED_EXECUTION_FLAGS)
    allowed_true_flags = ALLOWED_CONTROLLED_TRUE_FLAGS.get(evidence_id, set())
    unexpected_true_flags = [flag for flag in true_execution_flags if flag not in allowed_true_flags]
    if unexpected_true_flags:
        blocking_reasons.extend([f"unexpected_true_flag:{flag}" for flag in unexpected_true_flags])

    true_optional_flags = _extract_true_flags(payload, OPTIONAL_BLOCKING_FLAGS)
    if true_optional_flags:
        blocking_reasons.extend([f"unexpected_execution_flag:{flag}" for flag in true_optional_flags])

    source_status = str(payload.get("status", "")).strip().lower()
    if source_status not in STATUS_VOCABULARY:
        warnings.append("source_status_unknown")

    if source_status == "blocked":
        blocking_reasons.append("upstream_status_blocked")
    elif source_status in {"skipped", "failed"}:
        warnings.append(f"upstream_status:{source_status}")

    final_status = "blocked" if blocking_reasons else ("partial" if source_status in {"partial", "success"} else "skipped")

    return {
        "evidence_id": evidence_id,
        "status": final_status,
        "directory": _safe_path_text(directory),
        "latest_json_path": _safe_path_text(latest_json),
        "latest_json_present": True,
        "content_read": True,
        "missing_conditions": [] if final_status != "skipped" else [f"upstream_status:{source_status or 'missing'}"],
        "blocking_reasons": sorted(set(blocking_reasons)),
        "warnings": sorted(set(warnings)),
        "safe_summary": _sanitize_payload_summary(payload),
    }


def _historical_real_llm_verified(report_dir: str | Path | None = None) -> bool:
    root = Path(report_dir) if report_dir is not None else DEFAULT_EVIDENCE_DIRS["real_integration_staging_smoke"]
    if not root.exists() or not root.is_dir():
        return False
    for item in root.glob("*.json"):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("status") == "success"
            and payload.get("real_llm_executed") is True
            and payload.get("secret_plaintext_output") is not True
        ):
            return True
    return False


def _verified_domains(evidence_items: list[dict[str, Any]], historical_llm_report_dir: str | Path | None = None) -> set[str]:
    verified: set[str] = set()
    for item in evidence_items:
        summary = item.get("safe_summary", {})
        if not isinstance(summary, dict):
            continue
        if summary.get("real_llm_executed") is True:
            verified.add("real_llm")
        if summary.get("database_connected") is True or summary.get("migration_executed") is True:
            verified.add("postgres")
        if summary.get("redis_connected") is True:
            verified.add("redis")
        if summary.get("external_mcp_connected") is True:
            verified.add("external_mcp")
    if _historical_real_llm_verified(historical_llm_report_dir):
        verified.add("real_llm")
    return verified


def _derive_overall_status(evidence_items: list[dict[str, Any]], historical_llm_report_dir: str | Path | None = None) -> str:
    statuses = [item["status"] for item in evidence_items]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if {"real_llm", "postgres", "redis", "external_mcp"}.issubset(
        _verified_domains(evidence_items, historical_llm_report_dir)
    ):
        return "partial"
    if any(status == "skipped" for status in statuses):
        return "skipped"
    return "partial"


def _go_no_go_decision(status: str) -> dict[str, Any]:
    return {
        "combined_staging_gate": "Manual-Review" if status == "partial" else "Needs-Input",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 组合真实集成 Staging Gate（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- phase: {payload.get('phase', '')}",
        f"- status: {payload.get('status', '')}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        f"- database_connected: {payload.get('database_connected', False)}",
        f"- redis_connected: {payload.get('redis_connected', False)}",
        f"- external_mcp_connected: {payload.get('external_mcp_connected', False)}",
        f"- migration_executed: {payload.get('migration_executed', False)}",
        f"- business_data_written: {payload.get('business_data_written', False)}",
        f"- audit_data_written: {payload.get('audit_data_written', False)}",
        f"- metrics_data_written: {payload.get('metrics_data_written', False)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## Go/No-Go",
        f"- combined_staging_gate: {payload.get('go_no_go', {}).get('combined_staging_gate', '')}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        "",
        "## 证据索引",
    ]
    for item in payload.get("evidence_index", []):
        lines.extend(
            [
                f"### {item.get('evidence_id', '')}",
                f"- status: {item.get('status', '')}",
                f"- latest_json_present: {item.get('latest_json_present', False)}",
                f"- latest_json_path: {item.get('latest_json_path', '')}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                f"- blocking_reasons: {json.dumps(item.get('blocking_reasons', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_integration_staging_gate(
    *,
    output_dir: str | Path | None = None,
    evidence_dirs: dict[str, str | Path] | None = None,
    historical_llm_report_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    effective_dirs = {
        key: Path(value) for key, value in (evidence_dirs or DEFAULT_EVIDENCE_DIRS).items()
    }
    evidence_items = [
        _index_evidence("real_integration_env_profile", effective_dirs["real_integration_env_profile"]),
        _index_evidence("real_integration_smoke_plan", effective_dirs["real_integration_smoke_plan"]),
        _index_evidence("real_integration_staging_smoke", effective_dirs["real_integration_staging_smoke"]),
        _index_evidence("real_integration_readiness", effective_dirs["real_integration_readiness"]),
        _index_evidence("real_llm_provider_acceptance_gate", effective_dirs["real_llm_provider_acceptance_gate"]),
        _index_evidence("external_mcp_acceptance_gate", effective_dirs["external_mcp_acceptance_gate"]),
        _index_evidence("store_redis_readiness_drill", effective_dirs["store_redis_readiness_drill"]),
        _index_evidence("production_migration_drill", effective_dirs["production_migration_drill"]),
    ]

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    status = _derive_overall_status(evidence_items, historical_llm_report_dir)
    missing_conditions = sorted(
        {condition for item in evidence_items for condition in item.get("missing_conditions", [])}
    )
    blocked_reasons = sorted(
        {reason for item in evidence_items for reason in item.get("blocking_reasons", [])}
    )
    warnings = sorted({warning for item in evidence_items for warning in item.get("warnings", [])})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.2",
        "phase": "v4.4 Phase 24.5",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "evidence_index": evidence_items,
        "required_evidence_ids": list(DEFAULT_EVIDENCE_DIRS.keys()),
        "evidence_count": len(evidence_items),
        "missing_conditions": missing_conditions,
        "blocking_reasons": blocked_reasons,
        "warnings": warnings,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "go_no_go": _go_no_go_decision(status),
        "recommended_next_actions": [
            "先补齐 env profile、smoke plan 和缺失或 skipped 的单项证据，再重新生成组合 gate。",
            "若出现 blocked，先处理 secret 脱敏或异常执行 flag，再进入人工复核。",
            "所有证据齐全且脱敏后，组合 gate 仍只进入 Manual-Review，不自动放行公网生产直上。",
        ],
        "output_dir": str(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["blocking_reasons"] = sorted(set(payload["blocking_reasons"] + ["output:secret_like_text_detected"]))
        payload["go_no_go"]["combined_staging_gate"] = "Needs-Input"

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_staging_gate"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "read_only": True,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "evidence_count": len(evidence_items),
        "missing_count": len(payload["missing_conditions"]),
        "blocked_count": len(payload["blocking_reasons"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.4 组合真实集成 staging gate 报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--evidence-root",
        default=str(ROOT_DIR / "docs" / "reports"),
        help="证据根目录；默认按 docs/reports 下的六个固定子目录查找。",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_root = Path(args.evidence_root)
    summary = build_real_integration_staging_gate(
        output_dir=args.output_dir,
        evidence_dirs={
            key: evidence_root / Path(path).name
            for key, path in DEFAULT_EVIDENCE_DIRS.items()
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
