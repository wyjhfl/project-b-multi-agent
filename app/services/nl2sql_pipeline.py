from __future__ import annotations

from typing import Any

from app.agent.nl2sql.executor import SQLExecutionResult, SQLiteReadOnlyExecutor
from app.agent.nl2sql.formatter import SQLResultFormatter
from app.agent.nl2sql.generator import MockNL2SQLGenerator
from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import ProviderConfigError, UnknownProviderError, create_provider
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
                }
        else:
            gen = MockNL2SQLGenerator()

        result = gen.generate(query, schema)
        if isinstance(gen, LLMNL2SQLGenerator):
            provider_metadata = gen.last_provider_metadata

        self._record_token_usage("nl2sql", result.generator_used, provider_metadata)

        return {
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
