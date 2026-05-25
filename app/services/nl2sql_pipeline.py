from __future__ import annotations

import hashlib
import json
from typing import Any

from app.agent.nl2sql.executor import SQLExecutionResult, SQLiteReadOnlyExecutor
from app.agent.nl2sql.formatter import SQLResultFormatter
from app.agent.nl2sql.generator import MockNL2SQLGenerator
from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import ProviderConfigError, UnknownProviderError, create_provider
from app.core.config import settings
from app.harness.llm.budget import get_llm_budget_manager
from app.harness.llm.cache import build_nl2sql_cache_key, get_llm_result_cache
from app.harness.security.guardrails import GuardrailsEngine
from app.visualization.chart_planner import ChartPlanner


class NL2SQLPipeline:
    """NL2SQL Pipeline 服务

    preview(): 只生成 SQL + SQLGuard 校验，不执行 SQLite
    run(): 完整流程：query → schema → pruner → generator → guard → executor → formatter → chart
    所有错误进入 success=false + answer，不抛 500。
    """

    def __init__(self) -> None:
        self._metrics_recorder: Any | None = None
        self._guardrails = GuardrailsEngine()
        self._budget_manager = get_llm_budget_manager()
        self._cache = get_llm_result_cache()

    def set_metrics_recorder(self, recorder: Any) -> None:
        self._metrics_recorder = recorder

    def preview(
        self,
        query: str,
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
    ) -> dict:
        extractor = SchemaMetadataExtractor()
        schema = extractor.extract()

        gen_result = self._generate(query, schema, generator, provider, fallback_to_mock)
        output_guard = self._guardrails.sanitize_response(gen_result["reasoning"])
        if output_guard.get("sanitized_text"):
            gen_result["reasoning"] = output_guard["sanitized_text"]
        if output_guard.get("action") == "redact":
            gen_result["warnings"] = list(gen_result["warnings"]) + [
                f"guardrails_output_redact: {output_guard.get('reason', 'response contains pii')}"
            ]
        guardrails_info = {
            "output": output_guard,
        }

        return {
            "mode": "nl2sql_preview",
            "success": gen_result["guard_allowed"],
            "sql": gen_result["sql"],
            "selected_tables": gen_result["selected_tables"],
            "fallback": not gen_result["guard_allowed"],
            "guard_allowed": gen_result["guard_allowed"],
            "guard_reason": gen_result["guard_reason"],
            "reasoning": gen_result["reasoning"],
            "confidence": gen_result["confidence"],
            "generator_used": gen_result["generator_used"],
            "provider_used": gen_result["provider_used"],
            "fallback_used": gen_result["fallback_used"],
            "fallback_reason": gen_result["fallback_reason"],
            "warnings": gen_result["warnings"],
            "guardrails": guardrails_info,
        }

    def run(
        self,
        query: str,
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
    ) -> dict:
        preview_result = self.preview(query, generator, provider, fallback_to_mock)

        execution_dict = None
        formatted_dict = None
        chart_spec_dict = None
        planner = ChartPlanner()

        if preview_result["guard_allowed"] and preview_result["sql"]:
            executor = SQLiteReadOnlyExecutor()
            execution_result = executor.execute(preview_result["sql"])
            execution_dict = execution_result.model_dump()

            formatter = SQLResultFormatter()
            formatted_dict = formatter.format_summary(execution_result)

            chart_spec = planner.plan(execution_result, query)
            chart_spec_dict = chart_spec.model_dump()

            answer = formatted_dict.get("summary", "") if formatted_dict else ""
        else:
            execution_result = SQLExecutionResult(
                sql=preview_result["sql"],
                success=False,
                error=preview_result["guard_reason"],
            )
            execution_dict = execution_result.model_dump()
            formatted_dict = {
                "summary": f"查询执行失败: {preview_result['guard_reason']}",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
            }
            chart_spec = planner.plan(execution_result, query)
            chart_spec_dict = chart_spec.model_dump()

            answer = f"查询执行失败: {preview_result['guard_reason']}"

        return {
            "mode": "nl2sql",
            "success": preview_result["guard_allowed"],
            "answer": answer,
            "sql": preview_result["sql"],
            "selected_tables": preview_result["selected_tables"],
            "guard_allowed": preview_result["guard_allowed"],
            "guard_reason": preview_result["guard_reason"],
            "reasoning": preview_result["reasoning"],
            "confidence": preview_result["confidence"],
            "execution": execution_dict,
            "formatted_result": formatted_dict,
            "chart_spec": chart_spec_dict,
            "generator_used": preview_result["generator_used"],
            "provider_used": preview_result["provider_used"],
            "fallback_used": preview_result["fallback_used"],
            "fallback_reason": preview_result["fallback_reason"],
            "warnings": preview_result["warnings"],
            "guardrails": preview_result.get("guardrails"),
        }

    def _generate(
        self,
        query: str,
        schema: Any,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
    ) -> dict:
        provider_metadata: dict[str, Any] | None = None
        budget_status: dict[str, Any] | None = None
        cache_key: str | None = None
        if generator == "llm":
            try:
                prov = create_provider(provider)
                gen = LLMNL2SQLGenerator(provider=prov, fallback_to_mock=fallback_to_mock)
            except UnknownProviderError as exc:
                return {
                    "selected_tables": [],
                    "sql": "",
                    "guard_allowed": False,
                    "guard_reason": str(exc),
                    "reasoning": "",
                    "confidence": 0.0,
                    "generator_used": "llm",
                    "provider_used": provider,
                    "fallback_used": False,
                    "fallback_reason": str(exc),
                    "warnings": [],
                    "provider_metadata": None,
                    "budget_status": None,
                }
            except ProviderConfigError as exc:
                if fallback_to_mock:
                    gen = MockNL2SQLGenerator()
                    result = gen.generate(query, schema)
                    self._record_token_usage("nl2sql", "mock_fallback", None)
                    return {
                        "selected_tables": [t.name for t in result.pruned_schema.tables],
                        "sql": result.sql,
                        "guard_allowed": result.guard_result.allowed,
                        "guard_reason": result.guard_result.reason,
                        "reasoning": result.reasoning,
                        "confidence": result.confidence,
                        "generator_used": "mock_fallback",
                        "provider_used": "litellm",
                        "fallback_used": True,
                        "fallback_reason": str(exc),
                        "warnings": result.warnings,
                        "provider_metadata": None,
                        "budget_status": None,
                    }
                return {
                    "selected_tables": [],
                    "sql": "",
                    "guard_allowed": False,
                    "guard_reason": str(exc),
                    "reasoning": "",
                    "confidence": 0.0,
                    "generator_used": "llm",
                    "provider_used": "litellm",
                    "fallback_used": False,
                    "fallback_reason": str(exc),
                    "warnings": [],
                    "provider_metadata": None,
                    "budget_status": None,
                }

            provider_name = getattr(prov, "name", "unknown")
            provider_model = str(getattr(prov, "_model", "") or settings.llm_model or "")
            budget_status = self._budget_manager.check_budget(
                mode="nl2sql",
                provider=provider_name,
                model=provider_model,
                estimated_cost=0.0,
            )
            if self._metrics_recorder is not None:
                try:
                    self._metrics_recorder.set_budget_status("nl2sql", budget_status)
                except Exception:
                    pass
            if not budget_status.get("allowed", True):
                reason = str(budget_status.get("reason", "budget_blocked"))
                if fallback_to_mock:
                    mock_result = self._build_mock_fallback_result(query, schema, provider_name, reason)
                    return mock_result | {"budget_status": budget_status}
                return {
                    "selected_tables": [],
                    "sql": "",
                    "guard_allowed": False,
                    "guard_reason": reason,
                    "reasoning": f"预算限制拦截: {reason}",
                    "confidence": 0.0,
                    "generator_used": "llm",
                    "provider_used": provider_name,
                    "fallback_used": False,
                    "fallback_reason": reason,
                    "warnings": [reason],
                    "provider_metadata": None,
                    "budget_status": budget_status,
                }

            schema_hash = self._build_schema_hash(schema)
            cache_key = build_nl2sql_cache_key(
                query=query,
                schema_hash=schema_hash,
                prompt_version="nl2sql_prompt_v1",
                provider=provider_name,
                model=provider_model,
            )
            cached = self._cache.get(cache_key)
            if self._cache.enabled and self._metrics_recorder is not None:
                try:
                    if cached is None:
                        self._metrics_recorder.record_cache_miss("nl2sql")
                    else:
                        self._metrics_recorder.record_cache_hit("nl2sql")
                except Exception:
                    pass
            if cached is not None:
                cached_result = dict(cached)
                cached_warnings = list(cached_result.get("warnings") or [])
                if "cache_hit:nl2sql" not in cached_warnings:
                    cached_warnings.append("cache_hit:nl2sql")
                cached_result["warnings"] = cached_warnings
                cached_metadata = dict(cached_result.get("provider_metadata") or {})
                cached_metadata.update(
                    {
                        "cache_hit": True,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                    }
                )
                cached_result["provider_metadata"] = cached_metadata
                cached_result["budget_status"] = budget_status
                self._record_token_usage("nl2sql", cached_result.get("generator_used", "llm"), cached_metadata)
                return cached_result
        else:
            gen = MockNL2SQLGenerator()

        result = gen.generate(query, schema)
        if isinstance(gen, LLMNL2SQLGenerator):
            provider_metadata = gen.last_provider_metadata
            if provider_metadata:
                try:
                    self._budget_manager.record_usage(
                        mode="nl2sql",
                        provider=str(provider_metadata.get("provider", result.provider_used or "unknown")),
                        model=str(provider_metadata.get("model", "") or ""),
                        prompt_tokens=int(provider_metadata.get("prompt_tokens", 0) or 0),
                        completion_tokens=int(provider_metadata.get("completion_tokens", 0) or 0),
                        cost=float(provider_metadata.get("cost", 0.0) or 0.0),
                    )
                except Exception:
                    pass

        self._record_token_usage("nl2sql", result.generator_used, provider_metadata)
        output = {
            "selected_tables": [t.name for t in result.pruned_schema.tables],
            "sql": result.sql,
            "guard_allowed": result.guard_result.allowed,
            "guard_reason": result.guard_result.reason,
            "reasoning": result.reasoning,
            "confidence": result.confidence,
            "generator_used": result.generator_used,
            "provider_used": result.provider_used,
            "fallback_used": result.fallback_used,
            "fallback_reason": result.fallback_reason,
            "warnings": result.warnings,
            "provider_metadata": provider_metadata,
            "budget_status": budget_status,
        }
        if generator == "llm" and output["generator_used"] == "llm":
            try:
                if cache_key is not None:
                    self._cache.set(cache_key, output)
            except Exception:
                pass
        return output

    def _build_schema_hash(self, schema: Any) -> str:
        try:
            payload = []
            for table in getattr(schema, "tables", []) or []:
                payload.append(
                    {
                        "name": getattr(table, "name", ""),
                        "fields": [
                            {
                                "name": getattr(field, "name", ""),
                                "type": getattr(field, "type", ""),
                            }
                            for field in (getattr(table, "fields", []) or [])
                        ],
                    }
                )
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()
        except Exception:
            return "schema_hash_unavailable"

    def _build_mock_fallback_result(
        self,
        query: str,
        schema: Any,
        provider_name: str,
        reason: str,
    ) -> dict[str, Any]:
        gen = MockNL2SQLGenerator()
        result = gen.generate(query, schema)
        self._record_token_usage("nl2sql", "mock_fallback", None)
        return {
            "selected_tables": [t.name for t in result.pruned_schema.tables],
            "sql": result.sql,
            "guard_allowed": result.guard_result.allowed,
            "guard_reason": result.guard_result.reason,
            "reasoning": result.reasoning,
            "confidence": result.confidence,
            "generator_used": "mock_fallback",
            "provider_used": provider_name,
            "fallback_used": True,
            "fallback_reason": reason,
            "warnings": list(result.warnings) + [reason],
            "provider_metadata": None,
        }

    def _record_token_usage(self, task_id: str, generator_used: str, provider_metadata: dict[str, Any] | None) -> None:
        if self._metrics_recorder is None:
            return
        try:
            prompt_tokens = int((provider_metadata or {}).get("prompt_tokens", 0) or 0)
            completion_tokens = int((provider_metadata or {}).get("completion_tokens", 0) or 0)
            cost = float((provider_metadata or {}).get("cost", 0.0) or 0.0)
            self._metrics_recorder.record_token_usage(
                task_id=task_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
            )
        except Exception:
            pass
