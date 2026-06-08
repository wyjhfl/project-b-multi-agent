from __future__ import annotations

import json
import types

import pytest

from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import (
    FakeLLMProvider,
    LLMGenerateMetadata,
    LLMProvider,
    LiteLLMProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderModelError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    create_provider,
)
from app.core.config import settings
from app.agent.nl2sql.metadata import SchemaField, SchemaTable
from app.services.nl2sql_pipeline import NL2SQLPipeline


def _get_schema():
    return SchemaMetadataExtractor().extract()


def _get_schema_with_daily_metrics():
    schema = _get_schema()
    if any(t.name == "daily_metrics" for t in schema.tables):
        return schema
    synthetic_table = SchemaTable(
        name="daily_metrics",
        fields=[SchemaField(name="metric_date", type="TEXT", is_primary_key=False, sample_values=[])],
        row_count=1,
    )
    schema.tables.append(synthetic_table)
    return schema


def test_fake_llm_provider_metadata_complete():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata("今天GMV多少")
    assert metadata.provider == "fake"
    assert metadata.model == "fake-offline"
    assert isinstance(metadata.content, str)
    assert metadata.prompt_tokens == 0
    assert metadata.completion_tokens == 0
    assert metadata.total_tokens == 0
    assert metadata.cost == 0.0
    assert metadata.request_id == "fake-request"
    assert metadata.latency_ms >= 0
    assert metadata.error_type is None


def test_litellm_provider_no_key_raises_provider_config_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    with pytest.raises(ProviderConfigError):
        LiteLLMProvider()


def test_litellm_provider_import_error_is_clear(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    provider = LiteLLMProvider()
    monkeypatch.setattr(provider, "_import_litellm", lambda: (_ for _ in ()).throw(ProviderConfigError("需要安装 litellm")))
    with pytest.raises(ProviderConfigError, match="litellm"):
        provider.generate_with_metadata("hello")


def test_litellm_provider_success_with_usage_metadata(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    provider = LiteLLMProvider()

    usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    message = types.SimpleNamespace(content='{"sql":"SELECT 1","confidence":0.5,"reasoning":"ok","selected_tables":[]}')
    choice = types.SimpleNamespace(message=message)
    response = types.SimpleNamespace(
        usage=usage,
        choices=[choice],
        id="req-123",
        _hidden_params={"response_cost": 0.0025},
    )
    fake_litellm = types.SimpleNamespace(completion=lambda **_: response)
    monkeypatch.setattr(provider, "_import_litellm", lambda: fake_litellm)

    metadata = provider.generate_with_metadata("query")
    assert metadata.content.startswith("{")
    assert metadata.prompt_tokens == 11
    assert metadata.completion_tokens == 7
    assert metadata.total_tokens == 18
    assert metadata.cost == 0.0025
    assert metadata.request_id == "req-123"
    assert metadata.error_type is None


def test_litellm_provider_prefixes_openai_compatible_base_url_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mimo-v2.5-pro")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    captured: dict[str, str] = {}

    usage = types.SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    message = types.SimpleNamespace(content="ok")
    choice = types.SimpleNamespace(message=message)
    response = types.SimpleNamespace(
        usage=usage,
        choices=[choice],
        id="req-openai-compatible",
        _hidden_params={"response_cost": 0.0},
    )

    def _completion(**kwargs):
        captured["model"] = kwargs["model"]
        captured["api_base"] = kwargs["api_base"]
        return response

    provider = LiteLLMProvider(base_url="https://token-plan-cn.xiaomimimo.com/v1")
    monkeypatch.setattr(provider, "_import_litellm", lambda: types.SimpleNamespace(completion=_completion))

    metadata = provider.generate_with_metadata("hello")

    assert captured["model"] == "openai/mimo-v2.5-pro"
    assert captured["api_base"] == "https://token-plan-cn.xiaomimimo.com/v1"
    assert metadata.model == "mimo-v2.5-pro"


def test_litellm_provider_openai_compatible_fallback_normalizes_metadata(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mimo-v2.5-pro")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)

    class _Response:
        status_code = 200

        def json(self):
            return {
                "id": "req-xiaomi",
                "model": "mimo-v2.5-pro",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }

    captured: dict[str, object] = {}

    def _post(url, headers, json, timeout):
        captured["url"] = url
        captured["auth_header"] = headers["Authorization"]
        captured["model"] = json["model"]
        captured["timeout"] = timeout
        return _Response()

    provider = LiteLLMProvider(base_url="https://token-plan-cn.xiaomimimo.com/v1")
    monkeypatch.setattr("httpx.post", _post)

    metadata = provider._generate_openai_compatible("hello", 0.0)
    assert captured["url"] == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert captured["auth_header"] == "Bearer demo-key"
    assert captured["model"] == "mimo-v2.5-pro"
    assert metadata.content == "ok"
    assert metadata.model == "mimo-v2.5-pro"
    assert metadata.prompt_tokens == 3
    assert metadata.total_tokens == 5


def test_litellm_provider_openai_compatible_http_error_includes_safe_detail(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-5.5")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)

    class _Response:
        status_code = 400

        def json(self):
            return {
                "error": {
                    "code": "MODEL_NOT_FOUND",
                    "message": "model gpt-5.5 is unavailable",
                }
            }

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _Response())

    provider = LiteLLMProvider(base_url="http://100.119.206.22:8300/v1")
    with pytest.raises(ProviderResponseError) as exc_info:
        provider._generate_openai_compatible("hello", 0.0)

    detail = str(exc_info.value)
    assert "OpenAI-compatible endpoint returned 400" in detail
    assert "MODEL_NOT_FOUND" in detail
    assert "model gpt-5.5 is unavailable" in detail
    assert "demo-key" not in detail


def test_litellm_provider_openai_compatible_http_error_redacts_secret_detail(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-5.5")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "llm_max_retries", 0)

    class _Response:
        status_code = 400

        def json(self):
            return {
                "error": {
                    "code": "BAD_REQUEST",
                    "message": (
                        "upstream rejected sk-secret-value "
                        "at https://user:pass@example.test/v1?token=bad"
                    ),
                }
            }

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _Response())

    provider = LiteLLMProvider(base_url="http://100.119.206.22:8300/v1")
    with pytest.raises(ProviderResponseError) as exc_info:
        provider._generate_openai_compatible("hello", 0.0)

    detail = str(exc_info.value)
    assert "BAD_REQUEST" in detail
    assert "sk-secret-value" not in detail
    assert "token=bad" not in detail
    assert "user:pass" not in detail


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (Exception("authentication failed"), ProviderAuthError),
        (Exception("request timeout"), ProviderTimeoutError),
        (Exception("rate limit exceeded"), ProviderRateLimitError),
        (Exception("model not found"), ProviderModelError),
        (Exception("unknown response shape"), ProviderResponseError),
    ],
)
def test_litellm_provider_error_mapping(monkeypatch, exc: Exception, expected):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    provider = LiteLLMProvider()
    fake_litellm = types.SimpleNamespace(completion=lambda **_: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(provider, "_import_litellm", lambda: fake_litellm)
    with pytest.raises(expected):
        provider.generate_with_metadata("query")


def test_llm_generator_non_json_fallback():
    schema = _get_schema_with_daily_metrics()

    class BadProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "bad"

        def generate(self, prompt: str) -> str:
            return "not-json"

    generator = LLMNL2SQLGenerator(provider=BadProvider(), fallback_to_mock=True)
    result = generator.generate("今天GMV多少", schema)
    assert result.fallback_used is True
    assert result.generator_used == "mock_fallback"
    assert "invalid_json" in (result.fallback_reason or "")


def test_llm_generator_json_not_object_fallback():
    schema = _get_schema_with_daily_metrics()

    class BadProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "bad"

        def generate(self, prompt: str) -> str:
            return json.dumps(["not-object"])

    generator = LLMNL2SQLGenerator(provider=BadProvider(), fallback_to_mock=True)
    result = generator.generate("今天GMV多少", schema)
    assert result.fallback_used is True
    assert "not_object" in (result.fallback_reason or "")


def test_llm_generator_confidence_clamped_and_selected_tables_warning():
    schema = _get_schema_with_daily_metrics()

    class Provider(LLMProvider):
        @property
        def name(self) -> str:
            return "provider"

        def generate(self, prompt: str) -> str:
            return json.dumps(
                {
                    "sql": "SELECT metric_date, gmv FROM daily_metrics",
                    "confidence": 3.8,
                    "reasoning": 1,
                    "selected_tables": "daily_metrics",
                },
                ensure_ascii=False,
            )

        def generate_with_metadata(self, prompt: str):
            return LLMGenerateMetadata(
                content=self.generate(prompt),
                provider=self.name,
                model="x",
                prompt_tokens=2,
                completion_tokens=3,
                total_tokens=5,
                cost=0.01,
                request_id="r1",
                latency_ms=1.1,
                error_type=None,
            )

    generator = LLMNL2SQLGenerator(provider=Provider(), fallback_to_mock=False)
    result = generator.generate("今天GMV多少", schema)
    assert result.confidence == 1.0
    assert any("selected_tables 非 list" in w for w in result.warnings)


def test_llm_generator_dangerous_sql_blocked_by_guard():
    schema = _get_schema_with_daily_metrics()

    class Provider(LLMProvider):
        @property
        def name(self) -> str:
            return "provider"

        def generate(self, prompt: str) -> str:
            return json.dumps(
                {
                    "sql": "DELETE FROM orders",
                    "confidence": 0.8,
                    "reasoning": "dangerous",
                    "selected_tables": ["orders"],
                }
            )

    generator = LLMNL2SQLGenerator(provider=Provider(), fallback_to_mock=False)
    result = generator.generate("删除订单", schema)
    assert result.guard_result.allowed is False
    assert result.fallback_used is False
    assert "guard_blocked" in (result.fallback_reason or "")


def test_llm_generator_fallback_false_no_mock():
    schema = _get_schema_with_daily_metrics()

    class BadProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "bad"

        def generate(self, prompt: str) -> str:
            return "not-json"

    generator = LLMNL2SQLGenerator(provider=BadProvider(), fallback_to_mock=False)
    result = generator.generate("今天GMV多少", schema)
    assert result.fallback_used is False
    assert result.generator_used == "llm"
    assert result.guard_result.allowed is False


def test_pipeline_records_provider_metadata_tokens(monkeypatch):
    class RichProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "rich"

        def generate(self, prompt: str) -> str:
            return json.dumps(
                {
                    "sql": "SELECT metric_date, gmv FROM daily_metrics",
                    "confidence": 0.8,
                    "reasoning": "ok",
                    "selected_tables": ["daily_metrics"],
                }
            )

        def generate_with_metadata(self, prompt: str):
            return LLMGenerateMetadata(
                content=self.generate(prompt),
                provider=self.name,
                model="rich-model",
                prompt_tokens=20,
                completion_tokens=10,
                total_tokens=30,
                cost=0.12,
                request_id="rid",
                latency_ms=2.0,
                error_type=None,
            )

    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda _: RichProvider())
    pipeline = NL2SQLPipeline()

    class Recorder:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int, float]] = []

        def record_token_usage(self, task_id: str, prompt_tokens: int, completion_tokens: int, cost: float) -> None:
            self.calls.append((prompt_tokens, completion_tokens, cost))

    recorder = Recorder()
    pipeline.set_metrics_recorder(recorder)
    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert result["guard_allowed"] is True
    assert recorder.calls[-1] == (20, 10, 0.12)


def test_pipeline_fallback_false_no_execute(monkeypatch):
    class BadProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "bad"

        def generate(self, prompt: str) -> str:
            return "not-json"

    monkeypatch.setattr("app.services.nl2sql_pipeline.create_provider", lambda _: BadProvider())
    pipeline = NL2SQLPipeline()

    called = {"execute": 0}

    class DummyExecutor:
        def execute(self, sql: str):
            called["execute"] += 1
            raise AssertionError("不应执行 SQL")

    monkeypatch.setattr("app.services.nl2sql_pipeline.SQLiteReadOnlyExecutor", DummyExecutor)
    result = pipeline.run("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=False)
    assert result["guard_allowed"] is False
    assert called["execute"] == 0


def test_create_provider_unknown_provider_message():
    with pytest.raises(Exception, match="unknown provider"):
        create_provider("not-exists")


def test_create_provider_litellm_base_url_passed(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    provider = create_provider("litellm", base_url="https://mock-llm.local/v1")
    assert isinstance(provider, LiteLLMProvider)
    assert getattr(provider, "_base_url", "") == "https://mock-llm.local/v1"


def test_create_provider_litellm_empty_base_url_compatible(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_base_url", "")
    provider = create_provider("litellm")
    assert isinstance(provider, LiteLLMProvider)
    assert getattr(provider, "_base_url", "") == ""
