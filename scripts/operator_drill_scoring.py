from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "operator_drill_scoring"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
DIMENSIONS = [
    "availability",
    "recoverability",
    "evidence_integrity",
    "configuration_readiness",
    "permission_boundary",
    "known_limitations",
]

BOUNDARY_DECLARATIONS = [
    "只读操作员演练评分",
    "仅读取 JSON 元数据，不读取或输出报告正文",
    "不写业务数据",
    "不自动改变 Go/No-Go 结论",
    "不读取或输出真实 secret 原文",
    "默认 fake/offline",
    "默认 pytest/CI 不调用真实 LLM",
    "不执行真实外网 LLM",
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


def _status_score(status: str) -> int:
    return {
        "success": 100,
        "partial": 70,
        "skipped": 0,
        "blocked": 25,
        "failed": 0,
        "ready": 100,
    }.get(status, 0)


def _normalize_source_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("readiness_status") or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    return "partial" if raw else "skipped"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _load_source(label: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": label,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{label}:input_not_provided"],
            "warnings": [],
            "metadata": {},
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "name": label,
            "path": str(path),
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{label}:path_not_found"],
            "warnings": [],
            "metadata": {},
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": label,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{label}:json_file_required"],
            "warnings": [],
            "metadata": {},
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": label,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{label}:json_parse_failed"],
            "warnings": [f"{label}:json_parse_failed:{type(exc).__name__}"],
            "metadata": {},
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": label,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{label}:json_empty_or_not_object"],
            "warnings": [],
            "metadata": {},
        }

    status = _normalize_source_status(payload)
    missing = [str(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [str(item) for item in _safe_list(payload.get("warnings"))]
    skipped_reasons = [str(item) for item in _safe_list(payload.get("skipped_reasons"))]
    metadata: dict[str, Any] = {
        "status": status,
        "version": str(payload.get("version", "")),
        "mode": str(payload.get("mode", "")),
        "read_only": bool(payload.get("read_only", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "missing_condition_count": len(missing),
        "warning_count": len(warnings),
    }

    if label == "incident_report":
        scenarios = [item for item in _safe_list(payload.get("scenarios")) if isinstance(item, dict)]
        metadata["scenario_count"] = len(scenarios)
        metadata["scenario_status_counts"] = _count_statuses([str(item.get("status", "")) for item in scenarios])
    elif label == "handoff_report":
        items = [item for item in _safe_list(payload.get("handoff_items")) if isinstance(item, dict)]
        limitations = _safe_list(payload.get("known_limitations"))
        metadata["handoff_item_count"] = len(items)
        metadata["missing_item_count"] = len(_safe_list(payload.get("missing_items")))
        metadata["known_limitation_count"] = len(limitations)
    elif label == "integration_readiness":
        integrations = [item for item in _safe_list(payload.get("integrations")) if isinstance(item, dict)]
        metadata["integration_count"] = len(integrations)
        metadata["integration_status_counts"] = _count_statuses(
            [str(item.get("readiness_status") or item.get("status") or "") for item in integrations]
        )
    elif label == "evidence_comparison":
        comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
        metadata["added_count"] = _to_int(comparison.get("added_count"))
        metadata["removed_count"] = _to_int(comparison.get("removed_count"))
        metadata["changed_count"] = _to_int(comparison.get("changed_count"))

    if status == "skipped":
        missing.append(f"{label}:source_status_skipped")

    return {
        "name": label,
        "path": str(path),
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "missing_conditions": missing + skipped_reasons,
        "warnings": warnings,
        "metadata": metadata,
    }


def _count_statuses(statuses: list[str]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_VOCABULARY}
    for status in statuses:
        normalized = "success" if status == "ready" else status
        if normalized in counts:
            counts[normalized] += 1
    return counts


def _dimension(name: str, score: int, status: str, evidence: list[str], reason: str) -> dict[str, Any]:
    return {
        "dimension": name,
        "score": max(0, min(100, score)),
        "status": status if status in STATUS_VOCABULARY else "partial",
        "evidence_sources": evidence,
        "reason": reason,
    }


def _source_by_name(sources: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for source in sources:
        if source["name"] == name:
            return source
    return {"name": name, "loaded": False, "status": "skipped", "metadata": {}, "missing_conditions": []}


def _score_from_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incident = _source_by_name(sources, "incident_report")
    handoff = _source_by_name(sources, "handoff_report")
    readiness = _source_by_name(sources, "integration_readiness")
    comparison = _source_by_name(sources, "evidence_comparison")

    dimensions: list[dict[str, Any]] = []
    dimensions.append(
        _dimension(
            "availability",
            _status_score(incident["status"]),
            incident["status"],
            ["incident_report"],
            "基于故障演练报告整体状态和可用性场景元数据评分。",
        )
    )
    recoverability_status = _combine_dimension_status([incident["status"], handoff["status"]])
    dimensions.append(
        _dimension(
            "recoverability",
            round((_status_score(incident["status"]) + _status_score(handoff["status"])) / 2),
            recoverability_status,
            ["incident_report", "handoff_report"],
            "基于故障演练恢复路径和交接清单元数据评分。",
        )
    )
    dimensions.append(
        _dimension(
            "evidence_integrity",
            _status_score(comparison["status"]),
            comparison["status"],
            ["evidence_comparison"],
            "基于证据对比快照状态、变化计数和告警元数据评分。",
        )
    )
    dimensions.append(
        _dimension(
            "configuration_readiness",
            _status_score(readiness["status"]),
            readiness["status"],
            ["integration_readiness"],
            "基于可选集成准备度矩阵状态和缺失条件计数评分。",
        )
    )
    permission_status = _combine_dimension_status([handoff["status"], readiness["status"]])
    dimensions.append(
        _dimension(
            "permission_boundary",
            round((_status_score(handoff["status"]) + _status_score(readiness["status"])) / 2),
            permission_status,
            ["handoff_report", "integration_readiness"],
            "基于 RBAC/审批边界交接和集成启用边界元数据评分。",
        )
    )
    limitation_status = "success" if handoff.get("metadata", {}).get("known_limitation_count", 0) > 0 else handoff["status"]
    dimensions.append(
        _dimension(
            "known_limitations",
            100 if limitation_status == "success" else _status_score(limitation_status),
            limitation_status,
            ["handoff_report"],
            "基于交接报告是否保留已知限制和 Go/No-Go 边界说明评分。",
        )
    )
    return dimensions


def _combine_dimension_status(statuses: list[str]) -> str:
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses:
        return "partial"
    if "skipped" in statuses:
        return "skipped"
    return "success"


def _derive_status(*, loaded_count: int, dimensions: list[dict[str, Any]]) -> str:
    if loaded_count == 0:
        return "skipped"
    statuses = [str(item.get("status", "")) for item in dimensions]
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses or "skipped" in statuses:
        return "partial"
    return "success"


def _risk_level(overall_score: int, status: str) -> str:
    if status in {"failed", "blocked"} or overall_score < 40:
        return "high"
    if status in {"partial", "skipped"} or overall_score < 75:
        return "medium"
    return "low"


def _recommended_actions(status: str, missing_conditions: list[str], risk_level: str) -> list[str]:
    actions = [
        "保留默认 fake/offline 验收路径，未显式 opt-in 时不要执行真实外网 LLM。",
        "将评分结果作为操作员演练参考，不自动改变既有 Go/No-Go 结论。",
    ]
    if status == "skipped":
        actions.append("补充 incident/handoff/integration/evidence comparison JSON 输入后重新生成评分。")
    if any("source_status_skipped" in item for item in missing_conditions):
        actions.append("保留来源报告 skipped 语义，先补齐对应来源报告的缺失条件。")
    if risk_level != "low":
        actions.append("优先复核 availability、configuration_readiness 和 evidence_integrity 的低分维度。")
    return actions


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.5 操作员演练评分 Rubric（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- overall_score: {payload.get('overall_score', 0)}",
        f"- risk_level: {payload.get('risk_level', '')}",
        "",
        "## 评分维度",
    ]
    for item in payload.get("dimension_scores", []):
        lines.extend(
            [
                f"### {item.get('dimension', '')}",
                f"- score: {item.get('score', 0)}",
                f"- status: {item.get('status', '')}",
                f"- evidence_sources: {json.dumps(item.get('evidence_sources', []), ensure_ascii=False)}",
                f"- reason: {item.get('reason', '')}",
                "",
            ]
        )
    lines.append("## 缺失条件")
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## 建议动作"])
    for item in payload.get("recommended_actions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_operator_drill_scoring(
    *,
    output_dir: str | Path | None = None,
    incident_report: str | Path | None = None,
    handoff_report: str | Path | None = None,
    integration_readiness: str | Path | None = None,
    evidence_comparison: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    sources = [
        _load_source("incident_report", incident_report),
        _load_source("handoff_report", handoff_report),
        _load_source("integration_readiness", integration_readiness),
        _load_source("evidence_comparison", evidence_comparison),
    ]
    loaded_count = sum(1 for source in sources if source.get("loaded"))
    dimension_scores = _score_from_sources(sources)
    status = _derive_status(loaded_count=loaded_count, dimensions=dimension_scores)
    overall_score = 0 if loaded_count == 0 else round(sum(item["score"] for item in dimension_scores) / len(dimension_scores))
    risk = _risk_level(overall_score, status)
    missing_conditions = sorted({item for source in sources for item in source.get("missing_conditions", [])})
    warnings = sorted({item for source in sources for item in source.get("warnings", [])})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.4.0",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "input_sources": sources,
        "dimension_scores": dimension_scores,
        "overall_score": overall_score,
        "risk_level": risk,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "recommended_actions": _recommended_actions(status, missing_conditions, risk),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_operator_drill_scoring"
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
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "overall_score": overall_score,
        "risk_level": risk,
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.5 操作员演练评分 Rubric（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--incident-report", default=None)
    parser.add_argument("--handoff-report", default=None)
    parser.add_argument("--integration-readiness", default=None)
    parser.add_argument("--evidence-comparison", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_operator_drill_scoring(
        output_dir=args.output_dir,
        incident_report=args.incident_report,
        handoff_report=args.handoff_report,
        integration_readiness=args.integration_readiness,
        evidence_comparison=args.evidence_comparison,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
