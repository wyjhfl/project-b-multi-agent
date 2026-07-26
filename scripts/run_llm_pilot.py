"""真实模型试点运行器：preflight -> NL2SQL eval 抽样 -> 汇总 -> pilot_report 落盘。

诚实护栏（最高优先级）：
- 默认拒绝：未开启 real_llm_acceptance_enabled 或未配齐 provider/model/key 时，
  不生成任何报告，只打印配置指引，防止空跑产物被误当真实模型证据。
- --dry-run 用 fake provider 走通全流程，终端输出与报告均显著标注 DRY RUN。
- 报告统一经 pilot_report 脱敏落盘：不含 prompt 原文与密钥原文，base_url 仅保留 host 摘要。

环境变量（对齐现有 REAL_LLM_* 命名，PILOT_* 为单次运行的便捷覆盖）：
- REAL_LLM_ACCEPTANCE_ENABLED / REAL_LLM_PROVIDER / REAL_LLM_MODEL / REAL_LLM_BASE_URL
- REAL_LLM_API_KEY_ENV（默认 OPENAI_API_KEY，指向实际存放 key 的环境变量名）
- PILOT_PROVIDER / PILOT_MODEL / PILOT_BASE_URL / PILOT_API_KEY（优先级高于 REAL_LLM_*）
- REAL_LLM_PILOT_REPORT_DIR（报告输出目录，默认 docs/reports/real_llm_pilot）
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import FakeLLMProvider, LLMProvider, create_provider
from app.agent.nl2sql.sql_guard import SQLGuard
from app.core.config import settings
from app.harness.eval.cases import EvalCaseLoader, NL2SQLEvalCase
from app.harness.llm.pilot_report import (
    PilotReportCase,
    build_pilot_report,
    summarize_base_url,
    write_pilot_report_json,
    write_pilot_report_markdown,
)
from app.harness.llm.pilot_smoke_report import resolve_pilot_report_output_dir, resolve_smoke_commit

SUPPORTED_REAL_PROVIDERS = ("litellm", "openai_compatible")
DEFAULT_CASE_LIMIT = 20
NETWORK_PROBE_PROMPT = "请只返回: ok"
DRY_RUN_BANNER = "[run_llm_pilot] DRY RUN：provider=fake，仅验证流程，不构成真实模型证据。"


@dataclass
class PilotRunConfig:
    """一次试点运行的已解析配置（api_key 只在进程内传递，绝不落盘/打印）。"""

    mode: str
    provider: str
    model: str
    base_url: str
    api_key_env: str
    api_key: str

    @property
    def api_key_present(self) -> bool:
        return bool(self.api_key)


def resolve_pilot_config(dry_run: bool) -> PilotRunConfig:
    """解析运行配置：dry-run 强制 fake；真实模式 PILOT_* 覆盖 REAL_LLM_*。"""
    api_key_env = (settings.real_llm_api_key_env or "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"

    if dry_run:
        return PilotRunConfig(
            mode="dry_run",
            provider="fake",
            model="fake-offline",
            base_url="",
            api_key_env=api_key_env,
            api_key="",
        )

    provider = ((os.getenv("PILOT_PROVIDER", "") or "").strip() or (settings.real_llm_provider or "").strip()).lower()
    model = (os.getenv("PILOT_MODEL", "") or "").strip() or (settings.real_llm_model or "").strip()
    base_url = (os.getenv("PILOT_BASE_URL", "") or "").strip() or (settings.real_llm_base_url or "").strip()
    api_key = (os.getenv(api_key_env, "") or "").strip() or (os.getenv("PILOT_API_KEY", "") or "").strip()
    return PilotRunConfig(
        mode="real",
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        api_key=api_key,
    )


def collect_refusal_reasons(cfg: PilotRunConfig) -> list[str]:
    """真实模式的准入检查：任一不满足即拒绝生成报告。"""
    reasons: list[str] = []
    if not settings.real_llm_acceptance_enabled:
        reasons.append("real_llm_acceptance_enabled=false（需设置 REAL_LLM_ACCEPTANCE_ENABLED=true 显式开启真实试点）")
    if cfg.provider not in SUPPORTED_REAL_PROVIDERS:
        reasons.append(
            f"provider={cfg.provider or '<empty>'} 不在支持列表 {list(SUPPORTED_REAL_PROVIDERS)}"
            "（REAL_LLM_PROVIDER 或 PILOT_PROVIDER）"
        )
    if not cfg.model:
        reasons.append("model 为空（REAL_LLM_MODEL 或 PILOT_MODEL）")
    if cfg.provider == "openai_compatible" and not cfg.base_url:
        reasons.append("openai_compatible 需要 base_url（REAL_LLM_BASE_URL 或 PILOT_BASE_URL）")
    if not cfg.api_key_present:
        reasons.append(f"缺少 API Key：环境变量 {cfg.api_key_env}（或 PILOT_API_KEY）未设置")
    return reasons


def print_refusal_guidance(reasons: list[str]) -> None:
    print("[run_llm_pilot] 拒绝生成报告：真实 provider 未配置完整（诚实护栏，防止假报告冒充真实证据）。")
    print("原因:")
    for reason in reasons:
        print(f"  - {reason}")
    print("拿到 key 后（PowerShell 示例）:")
    print('  1. $env:REAL_LLM_ACCEPTANCE_ENABLED = "true"; $env:REAL_LLM_PROVIDER = "openai_compatible"')
    print('  2. $env:REAL_LLM_MODEL = "<model>"; $env:REAL_LLM_BASE_URL = "<https://.../v1>"; $env:OPENAI_API_KEY = "<key>"')
    print("  3. python scripts/run_llm_pilot.py")
    print("仅想演示流程: python scripts/run_llm_pilot.py --dry-run（报告显著标注 DRY RUN，不构成真实证据）")


def build_provider(cfg: PilotRunConfig) -> LLMProvider:
    if cfg.provider == "fake":
        return FakeLLMProvider()
    return create_provider(
        cfg.provider,
        api_key=cfg.api_key,
        model=cfg.model,
        base_url=cfg.base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        retry_backoff_seconds=settings.llm_retry_backoff_seconds,
        temperature=0.0,
    )


def run_pilot_preflight(cfg: PilotRunConfig, provider: LLMProvider, *, network_probe: bool = True) -> dict[str, Any]:
    """两阶段 preflight：配置检查 + 最小网络探测（dry-run 用 fake provider 同路径探测）。"""
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def _append(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    _append("run_mode", True, cfg.mode)
    provider_ok = cfg.provider in (("fake",) + SUPPORTED_REAL_PROVIDERS)
    _append("provider_supported", provider_ok, f"provider={cfg.provider or '<empty>'}")
    if not provider_ok:
        errors.append(f"unsupported provider: {cfg.provider or '<empty>'}")
    _append("model_configured", bool(cfg.model), f"model={'<set>' if cfg.model else '<empty>'}")
    _append(
        "api_key_present",
        cfg.api_key_present or cfg.mode == "dry_run",
        f"env={cfg.api_key_env} present={cfg.api_key_present}",
    )
    _append("base_url_summary", True, summarize_base_url(cfg.base_url))

    probe_latency_ms = 0.0
    if network_probe:
        try:
            metadata = provider.generate_with_metadata(NETWORK_PROBE_PROMPT)
            probe_latency_ms = float(getattr(metadata, "latency_ms", 0.0) or 0.0)
            probe_ok = bool((metadata.content or "").strip())
            _append("network_probe", probe_ok, f"latency_ms={probe_latency_ms:.2f}")
            if not probe_ok:
                errors.append("network_probe_empty_content")
        except Exception as exc:
            _append("network_probe", False, exc.__class__.__name__)
            errors.append(f"network_probe_failed:{exc.__class__.__name__}")
    else:
        _append("network_probe", True, "skipped")

    if errors:
        status = "failed"
    elif cfg.mode == "dry_run":
        status = "dry_run"
    else:
        status = "passed"
    return {"status": status, "checks": checks, "errors": errors, "probe_latency_ms": probe_latency_ms}


def _normal_case_passed(case: NL2SQLEvalCase, result: Any) -> tuple[bool, str]:
    """复用 NL2SQLEvalRunner 的判定口径，同时返回失败原因（不含 SQL/prompt 原文）。"""
    if not result.guard_result.allowed:
        return False, f"SQL 被拦截: {result.guard_result.reason}"

    reasons: list[str] = []
    selected_tables = [t.name for t in result.pruned_schema.tables]
    for expected_table in case.expected_tables:
        if expected_table not in selected_tables:
            reasons.append(f"缺少表 {expected_table}")
    for keyword in case.expected_sql_contains:
        if keyword.upper() not in result.sql.upper():
            reasons.append(f"SQL 缺少关键词 {keyword}")
    if reasons:
        return False, "; ".join(reasons)
    return True, ""


def _dangerous_case_passed(case: NL2SQLEvalCase, guard: SQLGuard) -> tuple[bool, str]:
    if not case.raw_sql:
        return False, "dangerous_sql case 缺少 raw_sql 字段"
    guard_result = guard.check(case.raw_sql)
    if guard_result.allowed:
        return False, "危险 SQL 未被拦截"
    if case.expected_blocked_keyword and case.expected_blocked_keyword.upper() not in guard_result.reason.upper():
        return False, f"拦截关键字不匹配: 期望 {case.expected_blocked_keyword}"
    return True, ""


def evaluate_cases(
    provider: LLMProvider,
    cases: list[NL2SQLEvalCase],
    *,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """逐条运行 eval 用例：dangerous_sql 走 SQLGuard，其余走 LLM 生成链路。"""
    schema = SchemaMetadataExtractor().extract(db_path)
    guard = SQLGuard()
    generator = LLMNL2SQLGenerator(provider=provider, fallback_to_mock=True)
    records: list[dict[str, Any]] = []

    for case in cases:
        if case.category == "dangerous_sql":
            passed, reason = _dangerous_case_passed(case, guard)
            records.append(
                {
                    "case_id": case.id,
                    "category": case.category,
                    "llm_called": False,
                    "passed": passed,
                    "fallback_used": False,
                    "fallback_reason": "",
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "request_id": "",
                    "warnings": [],
                    "outcome": "guard_blocked" if passed else "failed",
                    "reason": reason,
                }
            )
            continue

        result = generator.generate(case.input, schema)
        metadata = generator.last_provider_metadata or {}
        passed, reason = _normal_case_passed(case, result)
        if result.fallback_used:
            outcome = "fallback"
        elif passed:
            outcome = "success"
        else:
            outcome = "failed"
        records.append(
            {
                "case_id": case.id,
                "category": case.category,
                "llm_called": True,
                "passed": passed,
                "fallback_used": bool(result.fallback_used),
                "fallback_reason": str(result.fallback_reason or ""),
                "latency_ms": float(metadata.get("latency_ms") or 0.0),
                "prompt_tokens": int(metadata.get("prompt_tokens") or 0),
                "completion_tokens": int(metadata.get("completion_tokens") or 0),
                "total_tokens": int(metadata.get("total_tokens") or 0),
                "cost": float(metadata.get("cost") or 0.0),
                "request_id": str(metadata.get("request_id") or ""),
                "warnings": list(result.warnings or []),
                "outcome": outcome,
                "reason": reason,
            }
        )
    return records


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * ratio
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[int(rank)])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower))


def aggregate_eval_summary(cfg: PilotRunConfig, records: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总成功率/降级率/延迟分位/token 与成本，并收集 bad case（失败或降级）。"""
    llm_records = [r for r in records if r["llm_called"]]
    passed_cases = sum(1 for r in records if r["passed"])
    fallback_cases = sum(1 for r in llm_records if r["fallback_used"])
    latencies = [float(r["latency_ms"]) for r in llm_records if float(r["latency_ms"]) > 0.0]

    bad_cases = [
        {
            "case_id": r["case_id"],
            "category": r["category"],
            "outcome": r["outcome"],
            "reason": r["reason"] or r["fallback_reason"],
        }
        for r in records
        if (not r["passed"]) or r["fallback_used"]
    ]

    return {
        "run_mode": cfg.mode,
        "cases_total": len(records),
        "llm_called_cases": len(llm_records),
        "passed_cases": passed_cases,
        "success_rate": round(passed_cases / len(records), 4) if records else 0.0,
        "fallback_cases": fallback_cases,
        "fallback_rate": round(fallback_cases / len(llm_records), 4) if llm_records else 0.0,
        "latency_p50_ms": round(_percentile(latencies, 0.5), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
        "prompt_tokens_total": sum(int(r["prompt_tokens"]) for r in records),
        "completion_tokens_total": sum(int(r["completion_tokens"]) for r in records),
        "total_tokens_total": sum(int(r["total_tokens"]) for r in records),
        "cost_total_usd": round(sum(float(r["cost"]) for r in records), 6),
        "bad_cases": bad_cases,
    }


def build_report_cases(
    cfg: PilotRunConfig,
    records: list[dict[str, Any]],
    eval_summary: dict[str, Any],
    preflight: dict[str, Any],
) -> list[PilotReportCase]:
    """第一条为批量汇总案例（决定报告 provider/model/base_url 字段），其后为逐条明细。"""
    base_url_summary = summarize_base_url(cfg.base_url)
    dry_run = cfg.mode == "dry_run"
    evidence_notes = ["nl2sql_eval_pilot", "controlled_pilot"]
    if dry_run:
        evidence_notes.append("DRY_RUN_FAKE_PROVIDER")
    first_request_id = next((r["request_id"] for r in records if r["request_id"]), "")

    summary_case = PilotReportCase(
        scenario="nl2sql_eval_batch",
        endpoint="scripts/run_llm_pilot.py",
        request_id=first_request_id,
        provider=cfg.provider,
        model=cfg.model,
        base_url_summary=base_url_summary,
        api_key_env=cfg.api_key_env,
        api_key_present=cfg.api_key_present,
        real_call_attempted=not dry_run,
        real_call_succeeded=(not dry_run) and any(r["llm_called"] and not r["fallback_used"] for r in records),
        fallback_used=eval_summary["fallback_cases"] > 0,
        fallback_reason="see_case_details" if eval_summary["fallback_cases"] > 0 else "",
        budget_action="",
        cache_hit=False,
        latency_ms=float(eval_summary["latency_p50_ms"]),
        prompt_tokens=int(eval_summary["prompt_tokens_total"]),
        completion_tokens=int(eval_summary["completion_tokens_total"]),
        total_tokens=int(eval_summary["total_tokens_total"]),
        cost=float(eval_summary["cost_total_usd"]),
        error_type="",
        outcome="dry_run" if dry_run else "completed",
        warnings=[DRY_RUN_BANNER] if dry_run else [],
        evidence_links={},
        observability={"preflight_status": preflight["status"], "preflight_checks": preflight["checks"]},
        evidence_notes=evidence_notes,
        detail={"eval_summary": eval_summary},
    )

    case_entries = [
        PilotReportCase(
            scenario=f"nl2sql_eval:{r['case_id']}",
            endpoint="eval:nl2sql_cases",
            request_id=r["request_id"],
            provider=cfg.provider,
            model=cfg.model,
            base_url_summary=base_url_summary,
            api_key_env=cfg.api_key_env,
            api_key_present=cfg.api_key_present,
            real_call_attempted=(not dry_run) and r["llm_called"],
            real_call_succeeded=(not dry_run) and r["llm_called"] and not r["fallback_used"],
            fallback_used=r["fallback_used"],
            fallback_reason=r["fallback_reason"],
            budget_action="",
            cache_hit=False,
            latency_ms=float(r["latency_ms"]),
            prompt_tokens=int(r["prompt_tokens"]),
            completion_tokens=int(r["completion_tokens"]),
            total_tokens=int(r["total_tokens"]),
            cost=float(r["cost"]),
            error_type="",
            outcome=r["outcome"],
            warnings=list(r["warnings"]),
            evidence_links={},
            observability={},
            evidence_notes=evidence_notes,
            detail={"category": r["category"], "passed": r["passed"], "reason": r["reason"]},
        )
        for r in records
    ]
    return [summary_case, *case_entries]


def _resolve_output_dir(output_dir: str | None) -> Path | None:
    if output_dir:
        return Path(output_dir)
    return resolve_pilot_report_output_dir()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="真实模型试点：preflight + NL2SQL eval + 脱敏报告")
    parser.add_argument("--dry-run", action="store_true", help="用 fake provider 走通全流程（报告标注 DRY RUN）")
    parser.add_argument("--limit", type=int, default=DEFAULT_CASE_LIMIT, help="抽样用例数上限（默认 20）")
    parser.add_argument("--cases-path", default=None, help="eval 用例 JSON 路径（默认 data/evaluation/nl2sql_cases.json）")
    parser.add_argument("--db-path", default=None, help="schema 来源 SQLite 路径（默认 settings.ops_db_path）")
    parser.add_argument("--output-dir", default=None, help="报告输出目录（默认 REAL_LLM_PILOT_REPORT_DIR 或 docs/reports/real_llm_pilot）")
    parser.add_argument("--skip-network-probe", action="store_true", help="跳过 preflight 网络探测（仅排查用）")
    args = parser.parse_args(argv)

    cfg = resolve_pilot_config(args.dry_run)

    print("=== Real LLM Pilot (run_llm_pilot) ===")
    if cfg.mode == "dry_run":
        print(DRY_RUN_BANNER)
    print(f"provider/model: {cfg.provider} / {cfg.model or '<empty>'}")
    print(f"base_url: {summarize_base_url(cfg.base_url)}")
    print(f"api_key_env: {cfg.api_key_env} (present={cfg.api_key_present})")

    if cfg.mode == "real":
        reasons = collect_refusal_reasons(cfg)
        if reasons:
            print_refusal_guidance(reasons)
            return 2

    try:
        provider = build_provider(cfg)
    except Exception as exc:
        print(f"[run_llm_pilot] provider 初始化失败: {exc.__class__.__name__}")
        return 1

    preflight = run_pilot_preflight(cfg, provider, network_probe=not args.skip_network_probe)
    print(f"[preflight] status={preflight['status']}")
    for check in preflight["checks"]:
        flag = "ok" if check["ok"] else "FAIL"
        print(f"  [{flag}] {check['name']}: {check['detail']}")
    if preflight["errors"]:
        print("[run_llm_pilot] preflight 失败，不生成报告:")
        for error in preflight["errors"]:
            print(f"  - {error}")
        return 1

    cases = EvalCaseLoader().load(args.cases_path)
    if not cases:
        print("[run_llm_pilot] 未找到 eval 用例，不生成报告。")
        return 1
    sample = cases[: max(1, int(args.limit))]
    print(f"[eval] 运行 {len(sample)}/{len(cases)} 条用例 ...")

    records = evaluate_cases(provider, sample, db_path=args.db_path)
    for record in records:
        flag = "pass" if record["passed"] else "FAIL"
        print(
            f"  [{flag}] {record['case_id']} outcome={record['outcome']} "
            f"latency_ms={record['latency_ms']:.1f} tokens={record['total_tokens']} cost={record['cost']}"
        )

    eval_summary = aggregate_eval_summary(cfg, records)
    report = build_pilot_report(
        cases=build_report_cases(cfg, records, eval_summary, preflight),
        commit=resolve_smoke_commit(),
        environment=settings.app_env,
        report_id=f"llm-pilot-{cfg.mode.replace('_', '-')}",
    )
    payload = report.to_dict()
    payload["run_mode"] = cfg.mode
    payload["eval_summary"] = eval_summary

    output_dir = _resolve_output_dir(args.output_dir)
    json_path = write_pilot_report_json(payload, output_dir=output_dir)
    markdown_path = write_pilot_report_markdown(payload, output_dir=output_dir)

    print(
        "[summary] "
        f"success_rate={eval_summary['success_rate']} fallback_rate={eval_summary['fallback_rate']} "
        f"latency_p50_ms={eval_summary['latency_p50_ms']} latency_p95_ms={eval_summary['latency_p95_ms']} "
        f"tokens_total={eval_summary['total_tokens_total']} cost_total_usd={eval_summary['cost_total_usd']} "
        f"bad_cases={len(eval_summary['bad_cases'])}"
    )
    print(f"[report] json: {json_path}")
    print(f"[report] markdown: {markdown_path}")
    if cfg.mode == "dry_run":
        print(DRY_RUN_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
