from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from app.agent.nl2sql.executor import SQLiteReadOnlyExecutor
from app.agent.nl2sql.executor import SQLExecutionResult
from app.agent.nl2sql.formatter import SQLResultFormatter
from app.agent.nl2sql.generator import MockNL2SQLGenerator
from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.pruner import PrunedSchema, SchemaPruner
from app.agent.nl2sql.provider import FakeLLMProvider, LLMProvider, ProviderConfigError, UnknownProviderError, create_provider
from app.agent.nl2sql.sql_guard import SQLGuard
from app.harness.eval.cases import NL2SQLEvalCase
from app.harness.eval.nl2sql_runner import NL2SQLEvalRunner
from app.main import app

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")

client = TestClient(app)


def _get_schema():
    extractor = SchemaMetadataExtractor()
    return extractor.extract(DB_PATH)


def test_schema_extractor_reads_5_tables():
    schema = _get_schema()
    table_names = [t.name for t in schema.tables]
    assert "daily_metrics" in table_names
    assert "orders" in table_names
    assert "users" in table_names
    assert "products" in table_names
    assert "refund_orders" in table_names
    assert len(schema.tables) == 5


def test_schema_tables_have_fields_and_row_count():
    schema = _get_schema()
    for table in schema.tables:
        assert len(table.fields) > 0
        assert table.row_count >= 0


def test_pruner_gmv_selects_daily_metrics():
    schema = _get_schema()
    pruner = SchemaPruner()
    result = pruner.prune("今天GMV多少", schema)
    table_names = [t.name for t in result.tables]
    assert "daily_metrics" in table_names
    assert result.fallback is False


def test_pruner_top_products_selects_products_and_orders():
    schema = _get_schema()
    pruner = SchemaPruner()
    result = pruner.prune("Top商品有哪些", schema)
    table_names = [t.name for t in result.tables]
    assert "products" in table_names
    assert "orders" in table_names
    assert result.fallback is False


def test_pruner_refund_selects_refund_orders_and_orders():
    schema = _get_schema()
    pruner = SchemaPruner()
    result = pruner.prune("退款率是多少", schema)
    table_names = [t.name for t in result.tables]
    assert "refund_orders" in table_names
    assert "orders" in table_names
    assert result.fallback is False


def test_pruner_unmatched_returns_all_tables():
    schema = _get_schema()
    pruner = SchemaPruner()
    result = pruner.prune("今天天气怎么样", schema)
    assert result.fallback is True
    assert len(result.tables) == len(schema.tables)


def test_pruner_import_no_residual():
    import app.agent.nl2sql.pruner as pruner_mod
    assert not hasattr(pruner_mod, "PruneResult")


def test_sql_guard_allows_select():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders")
    assert result.allowed is True


def test_sql_guard_blocks_delete():
    guard = SQLGuard()
    result = guard.check("DELETE FROM orders")
    assert result.allowed is False
    assert "DELETE" in result.reason


def test_sql_guard_blocks_update():
    guard = SQLGuard()
    result = guard.check("UPDATE orders SET status='x'")
    assert result.allowed is False
    assert "UPDATE" in result.reason


def test_sql_guard_blocks_drop():
    guard = SQLGuard()
    result = guard.check("DROP TABLE orders")
    assert result.allowed is False
    assert "DROP" in result.reason


def test_sql_guard_auto_appends_limit():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders")
    assert result.allowed is True
    assert "LIMIT" in result.sql
    assert "100" in result.sql


def test_sql_guard_no_duplicate_limit():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders LIMIT 10")
    assert result.allowed is True
    assert result.sql.count("LIMIT") == 1


def test_sql_guard_blocks_empty_sql():
    guard = SQLGuard()
    result = guard.check("")
    assert result.allowed is False
    assert "空" in result.reason


def test_sql_guard_blocks_whitespace_sql():
    guard = SQLGuard()
    result = guard.check("   ")
    assert result.allowed is False
    assert "空" in result.reason


def test_sql_guard_blocks_multi_statement():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders; DROP TABLE users;")
    assert result.allowed is False
    assert "多条语句" in result.reason


def test_sql_guard_blocks_comment_with_dangerous_keyword():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders -- DELETE FROM users")
    assert result.allowed is False
    assert "注释" in result.reason
    assert "DELETE" in result.reason


def test_sql_guard_blocks_block_comment_with_dangerous_keyword():
    guard = SQLGuard()
    result = guard.check("SELECT * FROM orders /* DROP TABLE users */")
    assert result.allowed is False
    assert "注释" in result.reason
    assert "DROP" in result.reason


def test_sql_guard_allows_cte_with_select():
    guard = SQLGuard()
    result = guard.check("WITH recent AS (SELECT * FROM orders WHERE order_date = '2024-01-01') SELECT * FROM recent")
    assert result.allowed is True


def test_sql_guard_limit_not_confused_by_field_name():
    guard = SQLGuard()
    result = guard.check("SELECT limit_value FROM config")
    assert result.allowed is True
    assert result.sql.count("LIMIT") == 1


def test_mock_generator_gmv():
    schema = _get_schema()
    generator = MockNL2SQLGenerator()
    result = generator.generate("今天GMV多少", schema)
    assert result.sql != ""
    assert "daily_metrics" in result.sql
    assert result.confidence > 0
    assert result.guard_result.allowed is True


def test_mock_generator_new_users():
    schema = _get_schema()
    generator = MockNL2SQLGenerator()
    result = generator.generate("本月新增用户多少", schema)
    assert "users" in result.sql
    assert result.guard_result.allowed is True


def test_mock_generator_order_count():
    schema = _get_schema()
    generator = MockNL2SQLGenerator()
    result = generator.generate("今天订单量多少", schema)
    assert "orders" in result.sql
    assert result.guard_result.allowed is True


def test_mock_generator_top_products():
    schema = _get_schema()
    generator = MockNL2SQLGenerator()
    result = generator.generate("Top商品有哪些", schema)
    assert "products" in result.sql
    assert "orders" in result.sql
    assert result.guard_result.allowed is True


def test_mock_generator_refund_rate():
    schema = _get_schema()
    generator = MockNL2SQLGenerator()
    result = generator.generate("退款率是多少", schema)
    assert "refund_orders" in result.sql
    assert result.guard_result.allowed is True


def test_fake_llm_provider_returns_valid_json():
    provider = FakeLLMProvider()
    response = provider.generate("今天GMV多少")
    data = json.loads(response)
    assert "sql" in data
    assert "confidence" in data
    assert "reasoning" in data
    assert "selected_tables" in data


def test_llm_generator_gmv_with_fake_provider():
    schema = _get_schema()
    provider = FakeLLMProvider()
    generator = LLMNL2SQLGenerator(provider=provider)
    result = generator.generate("今天GMV多少", schema)
    assert result.guard_result.allowed is True
    assert "daily_metrics" in result.sql or "gmv" in result.sql.lower()


def test_llm_generator_top_products_with_fake_provider():
    schema = _get_schema()
    provider = FakeLLMProvider()
    generator = LLMNL2SQLGenerator(provider=provider)
    result = generator.generate("Top商品有哪些", schema)
    selected_tables = [t.name for t in result.pruned_schema.tables]
    assert "products" in selected_tables
    assert "orders" in selected_tables


def test_llm_generator_invalid_json_response():
    schema = _get_schema()

    class BadJSONProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "bad_json"

        def generate(self, prompt: str) -> str:
            return "this is not json"

    generator = LLMNL2SQLGenerator(provider=BadJSONProvider(), fallback_to_mock=False)
    result = generator.generate("今天GMV多少", schema)
    assert result.guard_result.allowed is False
    assert "非法 JSON" in result.guard_result.reason or "JSON" in result.guard_result.reason


def test_llm_generator_fallback_to_mock_on_error():
    schema = _get_schema()

    class ErrorProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "error"

        def generate(self, prompt: str) -> str:
            raise RuntimeError("LLM 服务不可用")

    generator = LLMNL2SQLGenerator(provider=ErrorProvider(), fallback_to_mock=True)
    result = generator.generate("今天GMV多少", schema)
    assert result.guard_result.allowed is True
    assert "[fallback from LLM error:" in result.reasoning


def test_llm_generator_no_fallback_returns_failure():
    schema = _get_schema()

    class ErrorProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "error"

        def generate(self, prompt: str) -> str:
            raise RuntimeError("LLM 服务不可用")

    generator = LLMNL2SQLGenerator(provider=ErrorProvider(), fallback_to_mock=False)
    result = generator.generate("今天GMV多少", schema)
    assert result.guard_result.allowed is False
    assert "LLM 调用失败" in result.guard_result.reason


def test_nl2sql_preview_api_default_mock():
    response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert "daily_metrics" in data["selected_tables"]
    assert data["fallback"] is False
    assert data["guard_allowed"] is True
    assert data["generator_used"] == "mock"


def test_nl2sql_preview_api_llm_generator():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "fake",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["generator_used"] in ("llm", "mock_fallback")
    assert data["provider_used"] == "fake"
    assert "confidence" in data
    assert "guard_reason" in data


def test_nl2sql_eval_api_default_mock():
    response = client.post("/nl2sql/eval")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 15
    assert data["accuracy"] >= 0.7
    assert data["generator_used"] == "mock"


def test_nl2sql_eval_api_llm_generator():
    response = client.post("/nl2sql/eval", json={"generator": "llm", "provider": "fake"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 15
    assert data["generator_used"] == "llm"
    assert data["provider_used"] == "fake"


def test_dangerous_sql_eval_uses_raw_sql():
    runner = NL2SQLEvalRunner()
    guard = SQLGuard()

    case = NL2SQLEvalCase(
        id="test_danger",
        input="删除订单",
        raw_sql="DELETE FROM orders",
        expected_blocked_keyword="DELETE",
        category="dangerous_sql",
    )

    guard_result = guard.check(case.raw_sql)
    assert guard_result.allowed is False
    assert "DELETE" in guard_result.reason

    passed = runner._check_dangerous_case(case)
    assert passed is True


def test_dangerous_sql_eval_select_not_blocked():
    runner = NL2SQLEvalRunner()

    case = NL2SQLEvalCase(
        id="test_false_danger",
        input="查询订单",
        raw_sql="SELECT * FROM orders",
        expected_blocked_keyword="DELETE",
        category="dangerous_sql",
    )

    passed = runner._check_dangerous_case(case)
    assert passed is False


def test_dangerous_sql_eval_not_affected_by_generator():
    runner_mock = NL2SQLEvalRunner(generator="mock")
    runner_llm = NL2SQLEvalRunner(generator="llm", provider="fake")

    case = NL2SQLEvalCase(
        id="test_danger_gen",
        input="删除订单",
        raw_sql="DELETE FROM orders",
        expected_blocked_keyword="DELETE",
        category="dangerous_sql",
    )

    assert runner_mock._check_dangerous_case(case) is True
    assert runner_llm._check_dangerous_case(case) is True


def test_v022_create_provider_fake():
    provider = create_provider("fake")
    assert isinstance(provider, FakeLLMProvider)
    assert provider.name == "fake"


def test_v022_create_provider_unknown_raises():
    import pytest
    with pytest.raises(UnknownProviderError, match="未知的 LLM Provider"):
        create_provider("unknown")


def test_v022_llm_generator_normal_fake_returns_observability():
    schema = _get_schema()
    provider = FakeLLMProvider()
    generator = LLMNL2SQLGenerator(provider=provider)
    result = generator.generate("今天GMV多少", schema)
    assert result.generator_used == "llm"
    assert result.provider_used == "fake"
    assert result.fallback_used is False


def test_v022_llm_generator_fallback_observability():
    schema = _get_schema()

    class ErrorProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "error"

        def generate(self, prompt: str) -> str:
            raise RuntimeError("LLM 服务不可用")

    generator = LLMNL2SQLGenerator(provider=ErrorProvider(), fallback_to_mock=True)
    result = generator.generate("今天GMV多少", schema)
    assert result.generator_used == "mock_fallback"
    assert result.fallback_used is True
    assert result.fallback_reason is not None
    assert "LLM 服务不可用" in result.fallback_reason


def test_v022_llm_generator_no_fallback_observability():
    schema = _get_schema()

    class ErrorProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "error"

        def generate(self, prompt: str) -> str:
            raise RuntimeError("LLM 服务不可用")

    generator = LLMNL2SQLGenerator(provider=ErrorProvider(), fallback_to_mock=False)
    result = generator.generate("今天GMV多少", schema)
    assert result.generator_used == "llm"
    assert result.fallback_used is False
    assert result.guard_result.allowed is False


def test_v022_llm_generator_extra_tables_warning():
    schema = _get_schema()

    class ExtraTablesProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "extra"

        def generate(self, prompt: str) -> str:
            return json.dumps({
                "sql": "SELECT * FROM nonexistent_table",
                "confidence": 0.7,
                "reasoning": "test",
                "selected_tables": ["nonexistent_table"],
            })

    generator = LLMNL2SQLGenerator(provider=ExtraTablesProvider())
    result = generator.generate("今天GMV多少", schema)
    assert len(result.warnings) > 0
    assert any("nonexistent_table" in w for w in result.warnings)


def test_v022_preview_api_llm_fake_provider():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "fake",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["provider_used"] == "fake"


def test_v022_preview_api_litellm_fallback_to_mock():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["generator_used"] == "mock_fallback"
    assert data["fallback_used"] is True


def test_v022_preview_api_litellm_no_fallback():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is False


def test_v022_eval_api_llm_fake_provider():
    response = client.post("/nl2sql/eval", json={
        "generator": "llm",
        "provider": "fake",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["provider_used"] == "fake"


def test_v022_dangerous_sql_not_affected_by_provider():
    runner = NL2SQLEvalRunner(generator="llm", provider="fake")
    case = NL2SQLEvalCase(
        id="test_danger_provider",
        input="删除订单",
        raw_sql="DELETE FROM orders",
        expected_blocked_keyword="DELETE",
        category="dangerous_sql",
    )
    assert runner._check_dangerous_case(case) is True


def test_v023_create_provider_unknown_raises_unknown_provider_error():
    import pytest
    with pytest.raises(UnknownProviderError):
        create_provider("unknown")


def test_v023_create_provider_litellm_no_key_raises_provider_config_error():
    import pytest
    from unittest.mock import patch
    with patch("app.agent.nl2sql.provider.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        mock_settings.llm_model = ""
        mock_settings.llm_provider = "litellm"
        with pytest.raises(ProviderConfigError):
            create_provider("litellm")


def test_v023_preview_unknown_provider_no_500():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "unknown",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is False
    assert "未知" in data["guard_reason"] or "unknown" in data["guard_reason"]


def test_v023_preview_litellm_fallback_true_returns_mock_fallback():
    response = client.post("/nl2sql/preview", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["generator_used"] == "mock_fallback"
    assert data["fallback_used"] is True


def test_v023_preview_litellm_fallback_false_returns_guard_not_allowed():
    from unittest.mock import patch
    with patch("app.agent.nl2sql.provider.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        mock_settings.llm_model = ""
        mock_settings.llm_provider = "litellm"
        response = client.post("/nl2sql/preview", json={
            "query": "今天GMV多少",
            "generator": "llm",
            "provider": "litellm",
            "fallback_to_mock": False,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is False
    assert "API_KEY" in data["guard_reason"] or "API Key" in data["guard_reason"]


def test_v023_eval_unknown_provider_no_500():
    response = client.post("/nl2sql/eval", json={
        "generator": "llm",
        "provider": "unknown",
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["failures"]) > 0
    assert any("未知" in f.get("reason", "") or "unknown" in f.get("reason", "").lower() for f in data["failures"])


def test_v023_eval_litellm_fallback_true_no_500():
    response = client.post("/nl2sql/eval", json={
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["fallback_count"] > 0


def test_v023_eval_litellm_fallback_false_no_500():
    from unittest.mock import patch
    with patch("app.agent.nl2sql.provider.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        mock_settings.llm_model = ""
        mock_settings.llm_provider = "litellm"
        response = client.post("/nl2sql/eval", json={
            "generator": "llm",
            "provider": "litellm",
            "fallback_to_mock": False,
        })
    assert response.status_code == 200
    data = response.json()
    assert len(data["failures"]) > 0
    assert any("API_KEY" in f.get("reason", "") or "API Key" in f.get("reason", "") for f in data["failures"])


def test_v023_executor_select_success():
    executor = SQLiteReadOnlyExecutor()
    result = executor.execute("SELECT * FROM orders")
    assert result.success is True
    assert len(result.columns) > 0
    assert result.row_count >= 0
    assert isinstance(result.rows, list)


def test_v023_executor_delete_blocked():
    executor = SQLiteReadOnlyExecutor()
    result = executor.execute("DELETE FROM orders")
    assert result.success is False
    assert "DELETE" in result.error


def test_v023_executor_multi_statement_blocked():
    executor = SQLiteReadOnlyExecutor()
    result = executor.execute("SELECT * FROM orders; DROP TABLE users;")
    assert result.success is False
    assert "多条语句" in result.error


def test_v023_executor_nonexistent_table_returns_failure():
    executor = SQLiteReadOnlyExecutor()
    result = executor.execute("SELECT * FROM nonexistent_table_xyz")
    assert result.success is False
    assert result.error is not None


def test_v023_formatter_single_metric_summary():
    from app.agent.nl2sql.executor import SQLExecutionResult
    execution = SQLExecutionResult(
        sql="SELECT COUNT(*) as total FROM orders",
        columns=["total"],
        rows=[{"total": 120}],
        row_count=1,
        success=True,
    )
    formatter = SQLResultFormatter()
    output = formatter.format_summary(execution)
    assert "total" in output["summary"]
    assert "120" in output["summary"]


def test_v023_formatter_multi_row_preserves_rows():
    from app.agent.nl2sql.executor import SQLExecutionResult
    execution = SQLExecutionResult(
        sql="SELECT name FROM products",
        columns=["name"],
        rows=[{"name": "A"}, {"name": "B"}, {"name": "C"}],
        row_count=3,
        success=True,
    )
    formatter = SQLResultFormatter()
    output = formatter.format_summary(execution)
    assert "3" in output["summary"]
    assert len(output["rows"]) == 3


def test_v023_execute_mock_gmv_success():
    response = client.post("/nl2sql/execute", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is True
    assert data["execution"] is not None
    assert data["execution"]["success"] is True
    assert data["formatted_result"] is not None
    assert "summary" in data["formatted_result"]


def test_v023_execute_top_products_multi_row():
    response = client.post("/nl2sql/execute", json={"query": "Top商品有哪些"})
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is True
    assert data["execution"]["success"] is True
    assert data["execution"]["row_count"] > 1


def test_v023_execute_unmatched_no_execution():
    response = client.post("/nl2sql/execute", json={"query": "今天天气怎么样"})
    assert response.status_code == 200
    data = response.json()
    assert data["guard_allowed"] is False
    assert data["execution"]["success"] is False


def test_v023_execute_llm_fake_provider():
    response = client.post("/nl2sql/execute", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "fake",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["execution"] is not None
    assert data["execution"]["success"] is True


def test_v023_execute_litellm_fallback_mock():
    response = client.post("/nl2sql/execute", json={
        "query": "今天GMV多少",
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["generator_used"] == "mock_fallback"
    assert data["execution"]["success"] is True


def test_v023_dangerous_sql_eval_no_execution():
    runner = NL2SQLEvalRunner(execute_sql=True)
    case = NL2SQLEvalCase(
        id="test_danger_exec",
        input="删除订单",
        raw_sql="DELETE FROM orders",
        expected_blocked_keyword="DELETE",
        category="dangerous_sql",
    )
    passed = runner._check_dangerous_case(case)
    assert passed is True
    stats = runner.run()
    assert stats.execution_passed > 0
    dangerous_cases = [c for c in runner._loader.load() if c.category == "dangerous_sql"]
    for dc in dangerous_cases:
        assert not dc.raw_sql or "DELETE" in dc.raw_sql or "DROP" in dc.raw_sql or "UPDATE" in dc.raw_sql


def test_v023_fallback_count_excludes_dangerous_sql():
    from unittest.mock import patch
    with patch("app.agent.nl2sql.provider.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        mock_settings.llm_model = ""
        mock_settings.llm_provider = "litellm"
        runner = NL2SQLEvalRunner(
            generator="llm",
            provider="litellm",
            fallback_to_mock=True,
        )
    assert runner._provider_error is not None
    stats = runner.run()
    dangerous_count = sum(1 for c in runner._loader.load() if c.category == "dangerous_sql")
    non_dangerous_count = stats.total - dangerous_count
    assert stats.fallback_count == non_dangerous_count


def test_v024_eval_execute_sql_true_returns_execution_passed():
    response = client.post("/nl2sql/eval", json={"execute_sql": True})
    assert response.status_code == 200
    data = response.json()
    assert data["execution_passed"] > 0


def test_v024_eval_execute_sql_false_returns_zero_execution():
    response = client.post("/nl2sql/eval", json={"execute_sql": False})
    assert response.status_code == 200
    data = response.json()
    assert data["execution_passed"] == 0
    assert data["execution_failed"] == 0


def test_v024_chart_planner_single_metric():
    from app.visualization.chart_planner import ChartPlanner
    execution = SQLExecutionResult(
        sql="SELECT COUNT(*) as total FROM orders",
        columns=["total"],
        rows=[{"total": 120}],
        row_count=1,
        success=True,
    )
    planner = ChartPlanner()
    spec = planner.plan(execution, "今天订单量多少")
    assert spec.chart_type == "metric"
    assert "total" in spec.y_fields


def test_v024_chart_planner_line_for_date_field():
    from app.visualization.chart_planner import ChartPlanner
    execution = SQLExecutionResult(
        sql="SELECT metric_date, gmv FROM daily_metrics",
        columns=["metric_date", "gmv"],
        rows=[{"metric_date": "2024-01-01", "gmv": 1000}, {"metric_date": "2024-01-02", "gmv": 1200}],
        row_count=2,
        success=True,
    )
    planner = ChartPlanner()
    spec = planner.plan(execution, "GMV趋势")
    assert spec.chart_type == "line"
    assert spec.x_field == "metric_date"
    assert "gmv" in spec.y_fields


def test_v024_chart_planner_bar_for_top_products():
    from app.visualization.chart_planner import ChartPlanner
    execution = SQLExecutionResult(
        sql="SELECT p.name, SUM(o.quantity) as total_qty FROM products p JOIN orders o GROUP BY p.name",
        columns=["name", "total_qty"],
        rows=[{"name": "商品A", "total_qty": 100}, {"name": "商品B", "total_qty": 80}],
        row_count=2,
        success=True,
    )
    planner = ChartPlanner()
    spec = planner.plan(execution, "Top商品")
    assert spec.chart_type == "bar"
    assert spec.x_field == "name"


def test_v024_chart_planner_failure_returns_table():
    from app.visualization.chart_planner import ChartPlanner
    execution = SQLExecutionResult(
        sql="DELETE FROM orders",
        success=False,
        error="SQL 包含危险操作: DELETE",
    )
    planner = ChartPlanner()
    spec = planner.plan(execution, "删除订单")
    assert spec.chart_type == "table"
    assert len(spec.data) == 0
    assert "失败" in spec.reason or "不可视化" in spec.reason


def test_v024_execute_gmv_returns_chart_spec():
    response = client.post("/nl2sql/execute", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["chart_spec"] is not None
    assert data["chart_spec"]["chart_type"] in ("metric", "table", "bar", "line", "pie")


def test_v024_execute_top_products_returns_bar_chart():
    response = client.post("/nl2sql/execute", json={"query": "Top商品有哪些"})
    assert response.status_code == 200
    data = response.json()
    assert data["chart_spec"] is not None
    assert data["chart_spec"]["chart_type"] in ("bar", "table")


def test_v024_execute_unmatched_returns_stable_chart_spec():
    response = client.post("/nl2sql/execute", json={"query": "今天天气怎么样"})
    assert response.status_code == 200
    data = response.json()
    assert data["chart_spec"] is not None
    assert data["chart_spec"]["chart_type"] == "table"


def test_v026_preview_returns_confidence():
    response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["confidence"] > 0


def test_v026_preview_returns_reasoning():
    response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["reasoning"]) > 0


def test_v026_preview_no_execution_fields():
    response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert "execution" not in data or data.get("execution") is None
    assert "formatted_result" not in data or data.get("formatted_result") is None
    assert "chart_spec" not in data or data.get("chart_spec") is None


def test_v026_preview_does_not_execute_sql():
    from unittest.mock import patch
    with patch("app.services.nl2sql_pipeline.SQLiteReadOnlyExecutor") as mock_executor_cls:
        mock_executor_cls.return_value.execute.side_effect = RuntimeError("executor should not be called")
        response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    mock_executor_cls.return_value.execute.assert_not_called()


def test_v026_execute_does_call_executor():
    response = client.post("/nl2sql/execute", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"] is not None
    assert data["execution"]["success"] is True


def test_v026_pipeline_preview_no_execution_field():
    from app.services.nl2sql_pipeline import NL2SQLPipeline
    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少")
    assert "execution" not in result
    assert "formatted_result" not in result
    assert "chart_spec" not in result
    assert result["mode"] == "nl2sql_preview"


def test_v026_pipeline_run_has_execution_fields():
    from app.services.nl2sql_pipeline import NL2SQLPipeline
    pipeline = NL2SQLPipeline()
    result = pipeline.run("今天GMV多少")
    assert "execution" in result
    assert "formatted_result" in result
    assert "chart_spec" in result
    assert result["mode"] == "nl2sql"
