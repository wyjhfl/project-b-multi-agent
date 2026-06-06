from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_gap_register"

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

ALLOWED_CONTROLLED_TRUE_FLAGS = {
    "real_integration_staging_smoke": {
        "real_llm_executed",
        "database_connected",
        "redis_connected",
        "external_mcp_connected",
    },
    "production_migration_drill": {"database_connected", "migration_executed"},
}

EVIDENCE_DIRS = {
    "real_integration_env_profile": ROOT_DIR / "docs" / "reports" / "real_integration_env_profile",
    "real_integration_smoke_plan": ROOT_DIR / "docs" / "reports" / "real_integration_smoke_plan",
    "real_integration_staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "real_integration_readiness": ROOT_DIR / "docs" / "reports" / "real_integration_readiness",
    "real_llm_provider_acceptance_gate": ROOT_DIR / "docs" / "reports" / "real_llm_provider_acceptance_gate",
    "external_mcp_acceptance_gate": ROOT_DIR / "docs" / "reports" / "external_mcp_acceptance_gate",
    "store_redis_readiness_drill": ROOT_DIR / "docs" / "reports" / "store_redis_readiness_drill",
    "real_integration_staging_gate": ROOT_DIR / "docs" / "reports" / "real_integration_staging_gate",
    "production_migration_drill": ROOT_DIR / "docs" / "reports" / "production_migration_drill",
}

DOMAIN_ACTIONS = {
    "real_llm": {
        "owner": "LLM 集成负责人",
        "next_action": "补齐 REAL_LLM opt-in 环境变量、模型名和密钥环境变量指针，然后执行受控 LLM preflight/smoke runbook。",
        "next_evidence": "real_llm_provider_acceptance_gate 报告从 skipped 进入 partial/manual review。",
    },
    "postgres": {
        "owner": "平台/数据负责人",
        "next_action": "准备受控 PostgreSQL staging 实例，配置 STORAGE_BACKEND=postgres 与 DATABASE_URL，并先通过 deployment guard。",
        "next_evidence": "store_redis_readiness_drill 与 staging gate 中 database 相关缺口消失。",
    },
    "redis": {
        "owner": "平台/缓存负责人",
        "next_action": "准备受控 Redis staging 实例，配置 REDIS_ENABLED=true、REDIS_URL 与 RATE_LIMIT_BACKEND=redis，并演练断连降级。",
        "next_evidence": "store_redis_readiness_drill 与 smoke plan 中 redis 条件进入 manual review。",
    },
    "external_mcp": {
        "owner": "MCP 集成负责人",
        "next_action": "明确 MCP_SERVER_COMMAND、command allowlist 与 tool allowlist，并保持所有调用经过 ToolGateway/PolicyEngine/审批/审计链路。",
        "next_evidence": "external_mcp_acceptance_gate 报告从 skipped 进入 partial/manual review。",
    },
    "combined_gate": {
        "owner": "技术总监/发布负责人",
        "next_action": "等待各单域证据补齐后重新生成组合 staging gate，并进入人工 Go/No-Go 评审。",
        "next_evidence": "real_integration_staging_gate evidence_count 完整且无 blocked/skipped。",
    },
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


def _safe_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "[redacted-secret-like-text]" if _contains_secret_like_text(text) else text


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    candidates = [path for path in directory.glob("*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=_json_report_sort_key)


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _rank_evidence_payload(evidence_id: str, payload: dict[str, Any]) -> tuple[int, int, str]:
    status = str(payload.get("status", "")).strip().lower()
    allowed_flags = ALLOWED_CONTROLLED_TRUE_FLAGS.get(evidence_id, set())
    controlled_true_count = sum(1 for flag in allowed_flags if payload.get(flag) is True)
    if status == "success" and controlled_true_count:
        return (4, controlled_true_count, status)
    if status == "success":
        return (3, controlled_true_count, status)
    if status == "partial":
        return (2, controlled_true_count, status)
    return (0, controlled_true_count, status)


def _select_evidence_json(evidence_id: str, directory: Path) -> tuple[Path, dict[str, Any]] | None:
    candidates: list[tuple[tuple[int, int, str], str, float, str, Path, dict[str, Any]]] = []
    if not directory.exists() or not directory.is_dir():
        return None
    for item in directory.glob("*.json"):
        if not item.is_file():
            continue
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
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


def _read_evidence(evidence_id: str, directory: Path) -> dict[str, Any]:
    selected = _select_evidence_json(evidence_id, directory)
    latest = _latest_json(directory)
    if selected is None:
        if latest is not None:
            return {
                "evidence_id": evidence_id,
                "status": "blocked",
                "latest_json_path": _safe_text(latest),
                "missing_conditions": [],
                "blocking_reasons": ["evidence_json_invalid"],
                "safe_summary": {},
            }
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "latest_json_path": None,
            "missing_conditions": [f"evidence:{evidence_id}:missing"],
            "blocking_reasons": [],
            "safe_summary": {},
        }
    latest, payload = selected

    blocking_reasons: list[str] = []
    if _contains_secret_like_text(payload):
        blocking_reasons.append("secret_like_content_detected")
    allowed_true_flags = ALLOWED_CONTROLLED_TRUE_FLAGS.get(evidence_id, set())
    for flag in CONTROLLED_EXECUTION_FLAGS:
        if payload.get(flag) is True and flag not in allowed_true_flags:
            blocking_reasons.append(f"unexpected_true_flag:{flag}")

    status = str(payload.get("status", "skipped")).strip().lower()
    if status not in STATUS_VOCABULARY:
        status = "skipped"
    if blocking_reasons:
        status = "blocked"

    missing_conditions = payload.get("missing_conditions", [])
    if not isinstance(missing_conditions, list):
        missing_conditions = []

    return {
        "evidence_id": evidence_id,
        "status": status,
        "latest_json_path": _safe_text(latest),
        "missing_conditions": sorted({str(item) for item in missing_conditions}),
        "blocking_reasons": sorted(set(blocking_reasons)),
        "safe_summary": {
            "generated_at": payload.get("generated_at"),
            "phase": payload.get("phase"),
            "version": payload.get("version"),
            "status": payload.get("status"),
            "read_only": payload.get("read_only"),
            "missing_count": len(missing_conditions),
            "blocked_count": len(blocking_reasons),
            "real_llm_executed": payload.get("real_llm_executed") is True,
            "database_connected": payload.get("database_connected") is True,
            "redis_connected": payload.get("redis_connected") is True,
            "external_mcp_connected": payload.get("external_mcp_connected") is True,
            "migration_executed": payload.get("migration_executed") is True,
        },
    }


def _domain_from_condition(condition: str, evidence_id: str) -> str:
    text = f"{evidence_id}:{condition}".lower()
    if "real_llm" in text or "llm" in text:
        return "real_llm"
    if "postgres" in text or "database" in text or "storage_backend" in text:
        return "postgres"
    if "redis" in text or "rate_limit_backend" in text:
        return "redis"
    if "mcp" in text:
        return "external_mcp"
    return "combined_gate"


def _build_gap_items(evidence_items: list[dict[str, Any]], historical_llm_report_dir: str | Path | None = None) -> list[dict[str, Any]]:
    verified_domains = _verified_domains(evidence_items, historical_llm_report_dir)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for evidence in evidence_items:
        evidence_id = evidence["evidence_id"]
        if evidence["status"] in {"skipped", "failed"} and not evidence.get("missing_conditions"):
            evidence["missing_conditions"] = [f"upstream_status:{evidence['status']}"]
        for condition in evidence.get("missing_conditions", []):
            if evidence["status"] in {"partial", "success"} and str(condition).startswith("upstream_status:"):
                continue
            domain = _domain_from_condition(condition, evidence_id)
            if str(condition) == "opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED" and {
                "postgres",
                "redis",
                "external_mcp",
            }.issubset(verified_domains):
                continue
            if domain in verified_domains:
                continue
            key = (domain, condition)
            action = DOMAIN_ACTIONS[domain]
            item = grouped.setdefault(
                key,
                {
                    "gap_id": f"{domain}:{condition}",
                    "domain": domain,
                    "condition": condition,
                    "status": "open",
                    "severity": "P1" if domain == "combined_gate" else "P0",
                    "owner": action["owner"],
                    "next_action": action["next_action"],
                    "next_evidence": action["next_evidence"],
                    "source_evidence_ids": [],
                },
            )
            item["source_evidence_ids"].append(evidence_id)
    for item in grouped.values():
        item["source_evidence_ids"] = sorted(set(item["source_evidence_ids"]))
    return sorted(grouped.values(), key=lambda item: (item["severity"], item["domain"], item["condition"]))


def _verified_domains(evidence_items: list[dict[str, Any]], historical_llm_report_dir: str | Path | None = None) -> set[str]:
    verified: set[str] = set()
    for evidence in evidence_items:
        summary = evidence.get("safe_summary", {})
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


def _historical_real_llm_verified(report_dir: str | Path | None = None) -> bool:
    report_dir = Path(report_dir) if report_dir is not None else EVIDENCE_DIRS["real_integration_staging_smoke"]
    if not report_dir.exists() or not report_dir.is_dir():
        return False
    for item in report_dir.glob("*.json"):
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


def _derive_status(evidence_items: list[dict[str, Any]], gap_items: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in evidence_items):
        return "blocked"
    if gap_items:
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 真实集成缺口登记表（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- phase: {payload.get('phase', '')}",
        f"- status: {payload.get('status', '')}",
        f"- gap_count: {payload.get('gap_count', 0)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        "",
        "## 缺口",
    ]
    for item in payload.get("gap_items", []):
        lines.extend(
            [
                f"### {item.get('gap_id', '')}",
                f"- domain: {item.get('domain', '')}",
                f"- severity: {item.get('severity', '')}",
                f"- owner: {item.get('owner', '')}",
                f"- next_action: {item.get('next_action', '')}",
                f"- next_evidence: {item.get('next_evidence', '')}",
                f"- source_evidence_ids: {json.dumps(item.get('source_evidence_ids', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.extend(
        [
            "## 边界声明",
            "- 本脚本只读取既有 JSON 证据字段，不连接真实 LLM、PostgreSQL、Redis 或 MCP Server。",
            "- 本脚本不执行 Alembic migration，不写业务/审计/指标数据，不读取或输出 secret 原文。",
            "- 缺口登记只作为后续受控执行入口，不代表真实生产验收完成。",
            "",
        ]
    )
    return "\n".join(lines)


def build_real_integration_gap_register(
    *,
    output_dir: str | Path | None = None,
    evidence_dirs: dict[str, str | Path] | None = None,
    historical_llm_report_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_dirs = {key: Path(value) for key, value in (evidence_dirs or EVIDENCE_DIRS).items()}
    evidence_items = [_read_evidence(evidence_id, directory) for evidence_id, directory in effective_dirs.items()]
    gap_items = _build_gap_items(evidence_items, historical_llm_report_dir)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.5",
        "phase": "v4.4 Phase 24.6 Real Integration Gap Register",
        "mode": "fake_offline_default",
        "status": _derive_status(evidence_items, gap_items),
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "evidence_index": evidence_items,
        "gap_items": gap_items,
        "gap_count": len(gap_items),
        "open_gap_count": len(gap_items),
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "go_no_go": {
            "combined_staging_gate": "Needs-Input" if gap_items else "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": _safe_text(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["gap_items"].append(
            {
                "gap_id": "combined_gate:output_secret_like_text_detected",
                "domain": "combined_gate",
                "condition": "output_secret_like_text_detected",
                "status": "open",
                "severity": "P0",
                "owner": DOMAIN_ACTIONS["combined_gate"]["owner"],
                "next_action": "先定位并移除证据中的 secret-like 文本，再重新生成缺口登记表。",
                "next_evidence": "gap register 不再出现 blocked 状态。",
                "source_evidence_ids": [],
            }
        )

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_gap_register"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

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
        "markdown_path": str(markdown_path),
        "output_dir": _safe_text(output_root),
        "evidence_count": len(evidence_items),
        "gap_count": payload["gap_count"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.4 真实集成缺口登记表（JSON + Markdown，只读）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--evidence-root", default=str(ROOT_DIR / "docs" / "reports"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_root = Path(args.evidence_root)
    summary = build_real_integration_gap_register(
        output_dir=args.output_dir,
        evidence_dirs={key: evidence_root / Path(path).name for key, path in EVIDENCE_DIRS.items()},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
