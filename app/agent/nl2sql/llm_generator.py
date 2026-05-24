from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from app.agent.nl2sql.generator import MockNL2SQLGenerator, NL2SQLResult
from app.agent.nl2sql.metadata import DatabaseSchema
from app.agent.nl2sql.pruner import SchemaPruner
from app.agent.nl2sql.provider import FakeLLMProvider, LLMProvider, create_provider
from app.agent.nl2sql.sql_guard import SQLGuard, SQLGuardResult


class LLMNL2SQLGenerator:
    """LLM 驱动的 NL2SQL 生成器

    通过 LLMProvider 生成 SQL，支持 fallback 到 MockNL2SQLGenerator。
    流程：query → SchemaPruner → 渲染 prompt → LLMProvider → 解析 JSON → SQLGuard → NL2SQLResult
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        fallback_to_mock: bool = True,
    ) -> None:
        self._provider = provider or FakeLLMProvider()
        self._pruner = SchemaPruner()
        self._guard = SQLGuard()
        self._mock_generator = MockNL2SQLGenerator()
        self._fallback_to_mock = fallback_to_mock
        self._prompt_template = self._load_prompt_template()

    def generate(self, query: str, schema: DatabaseSchema) -> NL2SQLResult:
        """根据用户查询生成 SQL

        Args:
            query: 用户查询
            schema: 数据库 schema

        Returns:
            NL2SQLResult
        """
        pruned = self._pruner.prune(query, schema)
        provider_name = self._provider.name

        try:
            prompt = self._render_prompt(query, pruned)
            raw_response = self._provider.generate(prompt)
            result = self._parse_response(query, pruned, raw_response, provider_name)
            return result
        except Exception as exc:
            if self._fallback_to_mock:
                mock_result = self._mock_generator.generate(query, schema)
                return NL2SQLResult(
                    query=mock_result.query,
                    pruned_schema=mock_result.pruned_schema,
                    sql=mock_result.sql,
                    confidence=mock_result.confidence,
                    reasoning=f"[fallback from LLM error: {exc}] {mock_result.reasoning}",
                    guard_result=mock_result.guard_result,
                    generator_used="mock_fallback",
                    provider_used=provider_name,
                    fallback_used=True,
                    fallback_reason=str(exc),
                    warnings=mock_result.warnings,
                )

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
                fallback_reason=None,
            )

    def _render_prompt(self, query: str, pruned: Any) -> str:
        schema_text = self._format_schema(pruned.tables)
        template = self._prompt_template or "{query}\n{schema_text}"
        return template.replace("{query}", query).replace("{schema_text}", schema_text)

    def _format_schema(self, tables: list[Any]) -> str:
        parts: list[str] = []
        for table in tables:
            fields_desc = ", ".join(
                f"{f.name}({f.type})" + (" PK" if f.is_primary_key else "")
                + (f" samples={f.sample_values}" if f.sample_values else "")
                for f in table.fields
            )
            parts.append(f"表 {table.name} ({table.row_count} 行): {fields_desc}")
        return "\n".join(parts)

    def _parse_response(self, query: str, pruned: Any, raw_response: str, provider_name: str) -> NL2SQLResult:
        warnings: list[str] = []

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            guard_result = SQLGuardResult(allowed=False, sql="", reason=f"LLM 返回非法 JSON: {exc}")
            return NL2SQLResult(
                query=query,
                pruned_schema=pruned,
                sql="",
                confidence=0.0,
                reasoning=f"LLM 返回非法 JSON: {exc}",
                guard_result=guard_result,
                generator_used="llm",
                provider_used=provider_name,
                fallback_used=False,
                warnings=[f"LLM 返回非法 JSON: {exc}"],
            )

        sql = data.get("sql", "")
        confidence = float(data.get("confidence", 0.0))
        reasoning = data.get("reasoning", "")
        selected_tables = data.get("selected_tables", [])

        if not sql:
            guard_result = SQLGuardResult(allowed=False, sql="", reason="LLM 返回空 SQL")
            return NL2SQLResult(
                query=query,
                pruned_schema=pruned,
                sql="",
                confidence=0.0,
                reasoning=reasoning or "LLM 返回空 SQL",
                guard_result=guard_result,
                generator_used="llm",
                provider_used=provider_name,
                fallback_used=False,
                warnings=["LLM 返回空 SQL"],
            )

        pruned_table_names = [t.name for t in pruned.tables]
        extra_tables = [t for t in selected_tables if t not in pruned_table_names]
        if extra_tables:
            warnings.append(f"LLM 选中了不在 pruned_schema 中的表: {extra_tables}")

        guard_result = self._guard.check(sql)

        return NL2SQLResult(
            query=query,
            pruned_schema=pruned,
            sql=guard_result.sql if guard_result.allowed else sql,
            confidence=confidence,
            reasoning=reasoning,
            guard_result=guard_result,
            generator_used="llm",
            provider_used=provider_name,
            fallback_used=False,
            warnings=warnings,
        )

    def _load_prompt_template(self) -> str | None:
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "nl2sql_prompt.md"
        )
        template_path = os.path.normpath(template_path)
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
