from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "pilot_closeout"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SOURCE_SPECS = [
    ("pilot_handoff", "handoff"),
    ("evidence_archive", "evidence"),
    ("integration_readiness", "integration"),
    ("operator_scoring", "operations"),
    ("controlled_integration", "integration"),
    ("governance_exceptions", "governance"),
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读试点收口报告包",
    "仅消费 JSON 元数据和结构化摘要字段，不读取报告正文",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
    "不连接真实外部 MCP",
    "不自动改变 Go/No-Go 结论",
    "不创建 GitHub Release",
    "不打 tag，不移动、不删除、不重建历史 tag",
    "当前版本保持 3.4.0，不写 3.5.0",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称真实 LLM 生产验收完成",
    "不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _normalize_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("readiness_status") or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    return "partial" if raw else "skipped"


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _load_source(name: str, scope: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "scope": scope,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "recommended_actions": [],
            "known_limitations": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "name": name,
            "scope": scope,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "recommended_actions": [],
            "known_limitations": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "scope": scope,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "recommended_actions": [],
            "known_limitations": [],
            "secret_detected": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": name,
            "scope": scope,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "recommended_actions": [],
            "known_limitations": [],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "scope": scope,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "recommended_actions": [],
            "known_limitations": [],
            "secret_detected": False,
        }

    status = _normalize_status(payload)
    secret_detected = _contains_secret_like_text(json.dumps(payload, ensure_ascii=False))
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    skipped_reasons = [_sanitize_text(item) for item in _safe_list(payload.get("skipped_reasons"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]
    recommended_actions = [_sanitize_text(item) for item in _safe_list(payload.get("recommended_actions"))]
    known_limitations = [_sanitize_text(item) for item in _safe_list(payload.get("known_limitations"))]

    if status == "skipped":
        missing_conditions.append(f"{name}:source_status_skipped")
    if payload.get("read_only") is False:
        missing_conditions.append(f"{name}:not_read_only")
    if bool(payload.get("real_llm_executed", False)):
        missing_conditions.append(f"{name}:real_llm_executed_unexpected")
    if bool(payload.get("external_mcp_connected", False)):
        missing_conditions.append(f"{name}:external_mcp_connected_unexpected")
    if secret_detected:
        missing_conditions.append(f"{name}:secret_like_value_detected")
        warnings.append(f"{name}:secret_like_value_detected")

    metadata = _extract_metadata(name, status, payload, missing_conditions, warnings, recommended_actions)

    return {
        "name": name,
        "scope": scope,
        "path": _sanitize_text(path),
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "metadata": metadata,
        "missing_conditions": missing_conditions + skipped_reasons,
        "warnings": warnings,
        "recommended_actions": recommended_actions,
        "known_limitations": known_limitations,
        "secret_detected": secret_detected,
    }


def _extract_metadata(
    name: str,
    status: str,
    payload: dict[str, Any],
    missing_conditions: list[str],
    warnings: list[str],
    recommended_actions: list[str],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "version": _sanitize_text(payload.get("version", "")),
        "mode": _sanitize_text(payload.get("mode", "")),
        "status": status,
        "read_only": bool(payload.get("read_only", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "missing_condition_count": len(missing_conditions),
        "warning_count": len(warnings),
        "recommended_action_count": len(recommended_actions),
    }
    if name == "pilot_handoff":
        metadata["handoff_item_count"] = len(_safe_list(payload.get("handoff_items")))
        metadata["missing_item_count"] = len(_safe_list(payload.get("missing_items")))
        go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
        metadata["go_no_go_summary"] = _sanitize_text(go_no_go.get("summary", ""))
        metadata["public_production_direct_launch"] = _sanitize_text(go_no_go.get("public_production_direct_launch", ""))
    elif name == "evidence_archive":
        metadata["manifest_id"] = _sanitize_text(payload.get("manifest_id", ""))
        metadata["total_files"] = _to_int(payload.get("total_files"))
        metadata["total_size_bytes"] = _to_int(payload.get("total_size_bytes"))
        metadata["missing_expected_type_count"] = len(_safe_list(payload.get("missing_expected_types")))
    elif name == "integration_readiness":
        integrations = [item for item in _safe_list(payload.get("integrations")) if isinstance(item, dict)]
        metadata["integration_count"] = len(integrations)
        metadata["readiness_status"] = _sanitize_text(payload.get("readiness_status", payload.get("status", "")))
    elif name == "operator_scoring":
        metadata["overall_score"] = _to_int(payload.get("overall_score"))
        metadata["risk_level"] = _sanitize_text(payload.get("risk_level", ""))
        metadata["dimension_count"] = len(_safe_list(payload.get("dimension_scores")))
    elif name == "controlled_integration":
        integrations = [item for item in _safe_list(payload.get("integrations")) if isinstance(item, dict)]
        metadata["integration_count"] = len(integrations)
        metadata["go_no_go_hint"] = _sanitize_text(payload.get("go_no_go_hint", ""))
    elif name == "governance_exceptions":
        metadata["exception_count"] = _to_int(payload.get("exception_count"))
        metadata["auto_approved"] = bool(payload.get("auto_approved", False))
    return metadata


def _derive_status(sources: list[dict[str, Any]]) -> str:
    loaded_sources = [source for source in sources if source.get("loaded")]
    if not loaded_sources:
        return "skipped"
    if any(source.get("secret_detected") for source in loaded_sources):
        return "blocked"
    if any(
        marker in condition
        for source in loaded_sources
        for condition in source.get("missing_conditions", [])
        for marker in [
            "real_llm_executed_unexpected",
            "external_mcp_connected_unexpected",
            "not_read_only",
        ]
    ):
        return "blocked"

    statuses = [str(source.get("status", "")) for source in loaded_sources]
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if all(status == "skipped" for status in statuses):
        return "skipped"
    if any(status in {"skipped", "partial"} for status in statuses) or len(loaded_sources) < len(sources):
        return "partial"
    return "success"


def _build_executive_summary(status: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    loaded_count = sum(1 for source in sources if source.get("loaded"))
    skipped_sources = [source["name"] for source in sources if source.get("status") == "skipped"]
    blocked_sources = [source["name"] for source in sources if source.get("status") == "blocked"]
    return {
        "summary": _summary_text(status, loaded_count, len(sources)),
        "loaded_source_count": loaded_count,
        "total_source_count": len(sources),
        "skipped_sources": skipped_sources,
        "blocked_sources": blocked_sources,
        "closeout_status": status,
    }


def _summary_text(status: str, loaded_count: int, total_count: int) -> str:
    if status == "blocked":
        return "试点收口证据存在阻断项，需要先人工关闭 blocked/secret/只读边界风险。"
    if status == "failed":
        return "试点收口证据存在 failed 状态，当前不能作为通过结论。"
    if status == "skipped":
        return "试点收口报告缺少可用输入或所有输入保持 skipped，本轮仅记录缺失条件。"
    if status == "partial":
        return f"试点收口报告已加载 {loaded_count}/{total_count} 个来源，仍需保留 skipped/partial 语义并人工复核。"
    return "试点收口报告来源元数据均为 success，但仍不代表公网生产直上或真实生产验收完成。"


def _build_evidence_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for source in sources:
        rows.append(
            {
                "name": source["name"],
                "scope": source["scope"],
                "loaded": bool(source.get("loaded")),
                "status": source.get("status", "skipped"),
                "metadata": source.get("metadata", {}),
                "missing_condition_count": len(source.get("missing_conditions", [])),
                "warning_count": len(source.get("warnings", [])),
            }
        )
    return {
        "source_count": len(rows),
        "loaded_count": sum(1 for item in rows if item["loaded"]),
        "sources": rows,
    }


def _build_go_no_go(status: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    if status in {"blocked", "failed"}:
        recommendation = "No-Go"
        rationale = "存在 blocked/failed 或边界风险，必须人工关闭后再复核。"
    elif status in {"skipped", "partial"}:
        recommendation = "Manual-Review"
        rationale = "存在缺失、skipped 或 partial 来源，不能伪造成通过。"
    else:
        recommendation = "Manual-Review"
        rationale = "来源元数据为 success 也只支持人工复核，不自动改变既有 Go/No-Go。"
    handoff = next((source for source in sources if source["name"] == "pilot_handoff"), {})
    return {
        "recommendation": recommendation,
        "rationale": rationale,
        "intranet_pilot": "人工复核后可继续",
        "public_production_direct_launch": "No-Go",
        "real_production_acceptance": "需另行执行",
        "source_go_no_go_summary": handoff.get("metadata", {}).get("go_no_go_summary", ""),
        "auto_changed": False,
    }


def _recommended_actions(status: str, sources: list[dict[str, Any]], missing_conditions: list[str]) -> list[str]:
    actions = [
        "将本报告包作为人工收口复核材料，不自动改变 Go/No-Go 结论。",
        "继续保持默认 fake/offline，未显式 opt-in 时不执行真实外网 LLM。",
        "复核所有 skipped/blocked 来源，保留原始状态语义并补齐缺失条件。",
    ]
    if status in {"blocked", "failed"}:
        actions.append("优先关闭 blocked/failed、secret-like、not_read_only 或真实外部执行相关风险。")
    if status == "skipped":
        actions.append("补充 pilot handoff、evidence archive、integration readiness、operator scoring、controlled integration 或 governance exception JSON 后重新生成。")
    for source in sources:
        actions.extend(str(item) for item in source.get("recommended_actions", [])[:3])
    if any("source_status_skipped" in item for item in missing_conditions):
        actions.append("来源报告为 skipped 时先补齐对应来源报告的输入或 opt-in 条件，不得在 closeout 中覆盖为 success。")
    return sorted({_sanitize_text(item) for item in actions})


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.5 试点收口报告包（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- status: {payload.get('status', '')}",
        f"- go_no_go: {payload.get('go_no_go', {}).get('recommendation', '')}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        "",
        "## Executive Summary",
        f"- {payload.get('executive_summary', {}).get('summary', '')}",
        "",
        "## Evidence Summary",
    ]
    for item in payload.get("evidence_summary", {}).get("sources", []):
        lines.append(
            f"- {item.get('name', '')}: status={item.get('status', '')}, "
            f"loaded={item.get('loaded', False)}, missing={item.get('missing_condition_count', 0)}"
        )
    lines.extend(["", "## Known Limitations"])
    for item in payload.get("known_limitations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Go/No-Go"])
    go_no_go = payload.get("go_no_go", {})
    lines.append(f"- recommendation: {go_no_go.get('recommendation', '')}")
    lines.append(f"- rationale: {go_no_go.get('rationale', '')}")
    lines.append(f"- public_production_direct_launch: {go_no_go.get('public_production_direct_launch', '')}")
    lines.extend(["", "## Next Actions"])
    for item in payload.get("next_actions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_pilot_closeout_report_pack(
    *,
    output_dir: str | Path | None = None,
    pilot_handoff: str | Path | None = None,
    evidence_archive: str | Path | None = None,
    integration_readiness: str | Path | None = None,
    operator_scoring: str | Path | None = None,
    controlled_integration: str | Path | None = None,
    governance_exceptions: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    source_paths = {
        "pilot_handoff": pilot_handoff,
        "evidence_archive": evidence_archive,
        "integration_readiness": integration_readiness,
        "operator_scoring": operator_scoring,
        "controlled_integration": controlled_integration,
        "governance_exceptions": governance_exceptions,
    }
    sources = [_load_source(name, scope, source_paths[name]) for name, scope in SOURCE_SPECS]
    status = _derive_status(sources)
    missing_conditions = sorted({item for source in sources for item in source.get("missing_conditions", [])})
    warnings = sorted({item for source in sources for item in source.get("warnings", [])})
    known_limitations = sorted(
        {
            item
            for source in sources
            for item in source.get("known_limitations", [])
        }
        | {
            "不宣称公网生产可直接上线。",
            "不宣称真实 LLM 生产验收完成。",
            "不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。",
            "真实生产验收、生产级 SSO/OIDC、多租户和复杂 BI 仍需后续专项验收。",
        }
    )

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.4.0",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "business_data_written": False,
        "release_created": False,
        "tag_created": False,
        "input_sources": sources,
        "executive_summary": _build_executive_summary(status, sources),
        "evidence_summary": _build_evidence_summary(sources),
        "known_limitations": known_limitations,
        "go_no_go": _build_go_no_go(status, sources),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "next_actions": _recommended_actions(status, sources, missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_pilot_closeout_report_pack"
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
        "external_mcp_connected": False,
        "business_data_written": False,
        "release_created": False,
        "tag_created": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.5 试点收口报告包（JSON + Markdown，只读）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--pilot-handoff", default=None)
    parser.add_argument("--evidence-archive", default=None)
    parser.add_argument("--integration-readiness", default=None)
    parser.add_argument("--operator-scoring", default=None)
    parser.add_argument("--controlled-integration", default=None)
    parser.add_argument("--governance-exceptions", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_pilot_closeout_report_pack(
        output_dir=args.output_dir,
        pilot_handoff=args.pilot_handoff,
        evidence_archive=args.evidence_archive,
        integration_readiness=args.integration_readiness,
        operator_scoring=args.operator_scoring,
        controlled_integration=args.controlled_integration,
        governance_exceptions=args.governance_exceptions,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
