from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.nl2sql.executor import SQLiteReadOnlyExecutor
from app.agent.nl2sql.generator import MockNL2SQLGenerator
from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import ProviderConfigError, UnknownProviderError, create_provider
from app.agent.nl2sql.sql_guard import SQLGuard
from app.harness.eval.cases import EvalCaseLoader, NL2SQLEvalCase


class EvalFailure(BaseModel):
    case_id: str = Field(..., description="用例 ID")
    input: str = Field(..., description="用户输入")
    reason: str = Field(default="", description="失败原因")


class EvalStats(BaseModel):
    total: int = Field(..., description="总用例数")
    passed: int = Field(..., description="通过数")
    failed: int = Field(..., description="失败数")
    accuracy: float = Field(..., description="准确率")
    failures: list[EvalFailure] = Field(default_factory=list, description="失败详情")
    generator_used: str = Field(default="mock", description="实际使用的生成器")
    provider_used: str | None = Field(default=None, description="使用的 LLM Provider 名称")
    fallback_count: int = Field(default=0, description="fallback 次数")
    execution_passed: int = Field(default=0, description="SQL 执行成功数")
    execution_failed: int = Field(default=0, description="SQL 执行失败数")


class NL2SQLEvalRunner:
    """NL2SQL 评测运行器

    批量执行评测样例，验证 schema pruning 和 SQL 生成。
    dangerous_sql case 直接调用 SQLGuard.check(raw_sql)，不走任何 generator。
    支持 mock 和 llm 两种 generator。
    """

    def __init__(
        self,
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
        execute_sql: bool = False,
    ) -> None:
        self._extractor = SchemaMetadataExtractor()
        self._generator_type = generator
        self._provider_name = provider
        self._fallback_to_mock = fallback_to_mock
        self._execute_sql = execute_sql
        self._provider_error: str | None = None
        self._generator = self._create_generator(generator, provider, fallback_to_mock)
        self._loader = EvalCaseLoader()
        self._guard = SQLGuard()
        self._executor = SQLiteReadOnlyExecutor() if execute_sql else None

    def _create_generator(self, generator: str, provider: str | None, fallback_to_mock: bool) -> Any:
        if generator == "llm":
            try:
                prov = create_provider(provider)
                return LLMNL2SQLGenerator(provider=prov, fallback_to_mock=fallback_to_mock)
            except ProviderConfigError as exc:
                if fallback_to_mock:
                    self._provider_error = str(exc)
                    return MockNL2SQLGenerator()
                raise
            except UnknownProviderError:
                raise
        return MockNL2SQLGenerator()

    def run(self, db_path: str | None = None, cases_path: str | None = None) -> EvalStats:
        schema = self._extractor.extract(db_path)
        cases = self._loader.load(cases_path)

        if not cases:
            return EvalStats(
                total=0, passed=0, failed=0, accuracy=0.0,
                generator_used=self._generator_type,
                provider_used=self._provider_name,
            )

        failures: list[EvalFailure] = []
        passed = 0
        fallback_count = 0
        execution_passed = 0
        execution_failed = 0
        generator_used = self._generator_type
        provider_used: str | None = self._provider_name

        if self._provider_error:
            generator_used = "mock_fallback"
            non_dangerous_count = sum(1 for c in cases if c.category != "dangerous_sql")
            fallback_count = non_dangerous_count

        for case in cases:
            if case.category == "dangerous_sql":
                case_passed = self._check_dangerous_case(case)
            else:
                result = self._generator.generate(case.input, schema)
                if result.fallback_used:
                    fallback_count += 1
                if result.generator_used and not self._provider_error:
                    generator_used = result.generator_used
                if result.provider_used and not self._provider_error:
                    provider_used = result.provider_used
                case_passed = self._check_normal_case(case, result)

                if self._executor and result.guard_result.allowed and result.sql:
                    exec_result = self._executor.execute(result.sql)
                    if exec_result.success:
                        execution_passed += 1
                    else:
                        execution_failed += 1

            if case_passed:
                passed += 1
            else:
                failures.append(EvalFailure(
                    case_id=case.id,
                    input=case.input,
                    reason=self._get_failure_reason(case),
                ))

        total = len(cases)
        accuracy = round(passed / total, 4) if total > 0 else 0.0

        return EvalStats(
            total=total,
            passed=passed,
            failed=total - passed,
            accuracy=accuracy,
            failures=failures,
            generator_used=generator_used,
            provider_used=provider_used,
            fallback_count=fallback_count,
            execution_passed=execution_passed,
            execution_failed=execution_failed,
        )

    def _check_dangerous_case(self, case: NL2SQLEvalCase) -> bool:
        if not case.raw_sql:
            return False

        guard_result = self._guard.check(case.raw_sql)

        if guard_result.allowed:
            return False

        if case.expected_blocked_keyword:
            return case.expected_blocked_keyword.upper() in guard_result.reason.upper()

        return True

    def _check_normal_case(self, case: NL2SQLEvalCase, result: Any) -> bool:
        if not result.guard_result.allowed:
            return False

        selected_tables = [t.name for t in result.pruned_schema.tables]

        for expected_table in case.expected_tables:
            if expected_table not in selected_tables:
                return False

        for keyword in case.expected_sql_contains:
            if keyword.upper() not in result.sql.upper():
                return False

        return True

    def _get_failure_reason(self, case: NL2SQLEvalCase) -> str:
        if case.category == "dangerous_sql":
            if not case.raw_sql:
                return "dangerous_sql case 缺少 raw_sql 字段"
            guard_result = self._guard.check(case.raw_sql)
            if guard_result.allowed:
                return f"危险 SQL 未被拦截: {case.raw_sql}"
            if case.expected_blocked_keyword and case.expected_blocked_keyword.upper() not in guard_result.reason.upper():
                return f"拦截关键字不匹配: 期望 {case.expected_blocked_keyword}, 实际 reason: {guard_result.reason}"
            return "未知原因"

        schema = self._extractor.extract()
        result = self._generator.generate(case.input, schema)

        reasons: list[str] = []

        if not result.guard_result.allowed:
            reasons.append(f"SQL 被拦截: {result.guard_result.reason}")
        else:
            selected_tables = [t.name for t in result.pruned_schema.tables]
            for expected_table in case.expected_tables:
                if expected_table not in selected_tables:
                    reasons.append(f"缺少表 {expected_table}，实际选中: {selected_tables}")

            for keyword in case.expected_sql_contains:
                if keyword.upper() not in result.sql.upper():
                    reasons.append(f"SQL 缺少关键词: {keyword}")

        return "; ".join(reasons) if reasons else "未知原因"
