from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from app.agent.nl2sql.generator import MockNL2SQLGenerator, NL2SQLResult
from app.agent.nl2sql.metadata import DatabaseSchema
from app.agent.nl2sql.pruner import SchemaPruner
from app.agent.nl2sql.provider import FakeLLMProvider, LLMGenerateMetadata, LLMProvider
from app.agent.nl2sql.sql_guard import SQLGuard, SQLGuardResult
from app.harness.security.guardrails import GuardrailsEngine


class LLMNL2SQLGenerator:
    """LLM 驱动的 NL2SQL 生成器。"""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        fallback_to_mock: bool = True,
    ) -> None:
        self._provider = provider or FakeLLMProvider()
        self._pruner = SchemaPruner()
        self._guard = SQLGuard()
        self._guardrails = GuardrailsEngine()
        self._mock_generator = MockNL2SQLGenerator()
        self._fallback_to_mock = fallback_to_mock
        self._prompt_template = self._load_prompt_template()
        self._last_provider_metadata: dict[str, Any] | None = None

    @property
    def last_provider_metadata(self) -> dict[str, Any] | None:
        return self._last_provider_metadata

    def generate(self, query: str, schema: DatabaseSchema) -> NL2SQLResult:
        pruned = self._pruner.prune(query, schema)
        provider_name = self._provider.name
        self._last_provider_metadata = None

        try:
            prompt = self._render_prompt(query, pruned)
            metadata = self._provider.generate_with_metadata(prompt)
            self._last_provider_metadata = asdict(metadata)
            return self._parse_response(query, schema, pruned, metadata, provider_name)
        except Exception as exc:
            return self._handle_generation_error(query, schema, pruned, provider_name, exc)

    def _handle_generation_error(
        self,
        query: str,
        schema: DatabaseSchema,
        pruned: Any,
        provider_name: str,
        exc: Exception,
    ) -> NL2SQLResult:
        reason = f"provider_error:{type(exc).__name__}:{exc}"
        if self._fallback_to_mock:
            return self._build_mock_fallback_result(query, schema, provider_name, reason)

        guard_result = SQLGuardResult(allowed=False, sql="", reason=f"LLM 调用失败: {exc}")
        return NL2SQLResult(
            query=query,
            pruned_schema=pruned,
            sql="",
            confidence=0.0,
            reasoning=f"LLM 调用失败: {exc}",
            guard_result=guard_result,
            generator_used="llm",
            provider_used=provider_name,
            fallback_used=False,
            fallback_reason=reason,
            warnings=[reason],
        )

    def _render_prompt(self, query: str, pruned: Any) -> str:
        schema_text = self._format_schema(pruned.tables)
        template = self._prompt_template or "{query}\n{schema_text}"
        return template.replace("{query}", query).replace("{schema_text}", schema_text)

    def _format_schema(self, tables: list[Any]) -> str:
        parts: list[str] = []
        for table in tables:
            fields_desc = ", ".join(
                f"{f.name}({f.type})"
                + (" PK" if f.is_primary_key else "")
                + (f" samples={f.sample_values}" if f.sample_values else "")
                for f in table.fields
            )
            parts.append(f"表 {table.name} ({table.row_count} 行): {fields_desc}")
        return "\n".join(parts)

    def _parse_response(
        self,
        query: str,
        schema: DatabaseSchema,
        pruned: Any,
        metadata: LLMGenerateMetadata,
        provider_name: str,
    ) -> NL2SQLResult:
        warnings: list[str] = []
        raw_response = metadata.content

        data, parse_warning, parse_error = self._loads_tolerant(raw_response)
        if parse_error is not None:
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                f"invalid_json:{parse_error}",
                warnings=[f"LLM 返回非法 JSON: {parse_error}"],
                schema=schema,
            )
        if parse_warning:
            warnings.append(parse_warning)

        if not isinstance(data, dict):
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                "invalid_payload:not_object",
                warnings=["LLM 返回 JSON 必须是 object"],
                schema=schema,
            )

        sql = data.get("sql")
        if not isinstance(sql, str):
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                "invalid_sql:not_string",
                warnings=["LLM 返回 sql 字段必须是 string"],
                schema=schema,
            )
        sql = sql.strip()
        if not sql:
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                "empty_sql",
                warnings=["LLM 返回空 SQL"],
                schema=schema,
            )

        confidence = 0.0
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            warnings.append("LLM 返回 confidence 非法，已使用默认值 0.0")
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        reasoning = data.get("reasoning", "")
        if not isinstance(reasoning, str):
            reasoning = ""
        if not reasoning:
            reasoning = "LLM 未提供 reasoning，已使用默认值。"

        llm_output_guard = self._guardrails.check_llm_output(reasoning)
        if llm_output_guard.get("sanitized_text"):
            reasoning = str(llm_output_guard["sanitized_text"])
        if llm_output_guard.get("action") in ("warn", "redact"):
            warnings.append(
                f"guardrails_output_{llm_output_guard['action']}: {llm_output_guard.get('reason', '')}"
            )
        if llm_output_guard.get("risk_level") == "high":
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                "dangerous_output_suggestion",
                warnings=warnings + ["LLM 输出包含危险操作建议"],
                schema=schema,
            )

        selected_tables_raw = data.get("selected_tables", [])
        selected_tables: list[str] = []
        if isinstance(selected_tables_raw, list):
            selected_tables = [str(t) for t in selected_tables_raw if isinstance(t, str)]
            if len(selected_tables) != len(selected_tables_raw):
                warnings.append("selected_tables 包含非字符串项，已忽略。")
        else:
            warnings.append("selected_tables 非 list，已重置为空列表。")

        pruned_table_names = [t.name for t in pruned.tables]
        extra_tables = [t for t in selected_tables if t not in pruned_table_names]
        if extra_tables:
            warnings.append(f"LLM 选择了不在 pruned_schema 的表: {extra_tables}")

        guard_result = self._guard.check(sql)
        if not guard_result.allowed:
            return self._fallback_or_failure(
                query,
                pruned,
                provider_name,
                f"guard_blocked:{guard_result.reason}",
                warnings=warnings + [f"SQLGuard 拦截: {guard_result.reason}"],
                schema=schema,
            )

        return NL2SQLResult(
            query=query,
            pruned_schema=pruned,
            sql=guard_result.sql,
            confidence=confidence,
            reasoning=reasoning,
            guard_result=guard_result,
            generator_used="llm",
            provider_used=provider_name,
            fallback_used=False,
            fallback_reason=None,
            warnings=warnings,
        )

    def _fallback_or_failure(
        self,
        query: str,
        pruned: Any,
        provider_name: str,
        fallback_reason: str,
        warnings: list[str],
        schema: DatabaseSchema | None,
    ) -> NL2SQLResult:
        if self._fallback_to_mock:
            if schema is None:
                raise RuntimeError("fallback_to_mock=true 时必须传入 schema。")
            return self._build_mock_fallback_result(
                query=query,
                schema=schema,
                provider_name=provider_name,
                fallback_reason=fallback_reason,
                extra_warnings=warnings,
            )

        guard_result = SQLGuardResult(allowed=False, sql="", reason=fallback_reason)
        human_reason = self._human_readable_reason(fallback_reason)
        return NL2SQLResult(
            query=query,
            pruned_schema=pruned,
            sql="",
            confidence=0.0,
            reasoning=human_reason,
            guard_result=SQLGuardResult(allowed=False, sql="", reason=human_reason),
            generator_used="llm",
            provider_used=provider_name,
            fallback_used=False,
            fallback_reason=fallback_reason,
            warnings=warnings,
        )

    def _build_mock_fallback_result(
        self,
        query: str,
        schema: DatabaseSchema,
        provider_name: str,
        fallback_reason: str,
        extra_warnings: list[str] | None = None,
    ) -> NL2SQLResult:
        mock_result = self._mock_generator.generate(query, schema)
        warnings = list(mock_result.warnings)
        if extra_warnings:
            warnings.extend(extra_warnings)
        return NL2SQLResult(
            query=mock_result.query,
            pruned_schema=mock_result.pruned_schema,
            sql=mock_result.sql,
            confidence=mock_result.confidence,
            reasoning=f"[fallback from LLM error: {fallback_reason}] {mock_result.reasoning}",
            guard_result=mock_result.guard_result,
            generator_used="mock_fallback",
            provider_used=provider_name,
            fallback_used=True,
            fallback_reason=fallback_reason,
            warnings=warnings,
        )

    @staticmethod
    def _loads_tolerant(raw: str) -> tuple[Any, str | None, json.JSONDecodeError | None]:
        """解析 LLM 返回的 JSON，容忍 markdown 代码围栏与前后缀说明文本。

        真实 provider 常把 JSON 包在 ```json 围栏中或附带解释文字，
        直接 json.loads 会整体降级；这里按 原样 -> 剥离围栏 -> 提取
        首尾大括号 三级尝试，成功时返回提示 warning，全部失败则返回
        首次解析错误。
        """
        try:
            return json.loads(raw), None, None
        except json.JSONDecodeError as exc:
            first_error = exc

        text = raw.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            stripped = text.rstrip()
            if stripped.endswith("```"):
                text = stripped[: -len("```")]
            try:
                return json.loads(text), "已从 markdown 代码围栏中提取 JSON", None
            except json.JSONDecodeError:
                pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1]), "已从含前后缀文本的响应中提取 JSON", None
            except json.JSONDecodeError:
                pass

        return None, None, first_error

    def _human_readable_reason(self, fallback_reason: str) -> str:
        if fallback_reason.startswith("invalid_json:"):
            return f"LLM 返回非法 JSON: {fallback_reason.split(':', 1)[1]}"
        if fallback_reason.startswith("invalid_payload:not_object"):
            return "LLM 返回 JSON 必须是 object。"
        if fallback_reason.startswith("invalid_sql:not_string"):
            return "LLM 返回 sql 字段必须是 string。"
        if fallback_reason.startswith("empty_sql"):
            return "LLM 返回空 SQL。"
        if fallback_reason.startswith("guard_blocked:"):
            return f"SQLGuard 拦截: {fallback_reason.split(':', 1)[1]}"
        return fallback_reason

    def _load_prompt_template(self) -> str | None:
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "nl2sql_prompt.md"
        )
        template_path = os.path.normpath(template_path)
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
