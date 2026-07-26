from __future__ import annotations

import json
import types

import httpx
import pytest

from app.agent.nl2sql.provider import (
    FakeLLMProvider,
    LiteLLMProvider,
    OpenAICompatibleProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    create_provider,
)
from app.core.config import settings
from app.harness.eval.judge import JudgeInput, LLMJudgeProvider
from app.harness.llm.budget import (
    LLMBudgetManager,
    estimate_llm_cost_usd,
    estimate_prompt_tokens,
    get_llm_budget_manager,
)
from app.main import reset_runtime_for_test
from app.services.nl2sql_pipeline import NL2SQLPipeline


_SQL_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行只读 SQL 查询",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    }
]


# ---------- FakeLLMProvider: function calling ----------


def test_fake_provider_tool_call_on_keyword_hit():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata("今天GMV多少", tools=_SQL_TOOLS)
    assert metadata.content == ""
    assert metadata.tool_calls is not None
    call = metadata.tool_calls[0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "execute_sql"
    arguments = json.loads(call["function"]["arguments"])
    assert "daily_metrics" in arguments["sql"]


def test_fake_provider_no_tool_call_without_keyword_hit():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata("完全无关的问题", tools=_SQL_TOOLS)
    assert metadata.tool_calls is None
    payload = json.loads(metadata.content)
    assert payload["sql"] == ""


def test_fake_provider_tool_choice_none_disables_tool_call():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata("今天GMV多少", tools=_SQL_TOOLS, tool_choice="none")
    assert metadata.tool_calls is None
    assert json.loads(metadata.content)["confidence"] == 0.9


def test_fake_provider_tool_choice_forces_named_tool():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata(
        "完全无关的问题",
        tools=_SQL_TOOLS,
        tool_choice={"type": "function", "function": {"name": "custom_tool"}},
    )
    assert metadata.tool_calls is not None
    assert metadata.tool_calls[0]["function"]["name"] == "custom_tool"
    assert json.loads(metadata.tool_calls[0]["function"]["arguments"])["sql"] == ""


def test_fake_provider_without_tools_keeps_legacy_behavior():
    provider = FakeLLMProvider()
    metadata = provider.generate_with_metadata("今天GMV多少")
    assert metadata.tool_calls is None
    assert metadata.to_dict()["tool_calls"] is None
    assert json.loads(metadata.content)["selected_tables"] == ["daily_metrics"]


# ---------- FakeLLMProvider: streaming ----------


def test_fake_provider_stream_chunks_join_to_full_content(monkeypatch):
    monkeypatch.setattr(settings, "llm_stream_chunk_chars", 8)
    provider = FakeLLMProvider()
    chunks = list(provider.generate_stream("今天GMV多少"))
    assert len(chunks) > 1
    assert all(len(chunk) <= 8 for chunk in chunks)
    metadata = provider.last_stream_metadata
    assert metadata is not None
    assert "".join(chunks) == metadata.content
    assert metadata.provider == "fake"
    assert json.loads(metadata.content)["selected_tables"] == ["daily_metrics"]


def test_fake_provider_stream_with_tools_reports_tool_calls(monkeypatch):
    monkeypatch.setattr(settings, "llm_stream_chunk_chars", 8)
    provider = FakeLLMProvider()
    chunks = list(provider.generate_stream("今天GMV多少", tools=_SQL_TOOLS))
    assert chunks == []
    metadata = provider.last_stream_metadata
    assert metadata is not None
    assert metadata.tool_calls is not None
    assert metadata.tool_calls[0]["function"]["name"] == "execute_sql"


# ---------- LiteLLMProvider: tools 透传与流式 ----------


def test_litellm_provider_passes_tools_and_parses_tool_calls(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    provider = LiteLLMProvider()

    captured: dict = {}
    tool_call = types.SimpleNamespace(
        id="call-1",
        type="function",
        function=types.SimpleNamespace(name="execute_sql", arguments='{"sql":"SELECT 1"}'),
    )
    message = types.SimpleNamespace(content=None, tool_calls=[tool_call])
    response = types.SimpleNamespace(
        usage=types.SimpleNamespace(prompt_tokens=9, completion_tokens=4, total_tokens=13),
        choices=[types.SimpleNamespace(message=message)],
        id="req-tools",
        _hidden_params={"response_cost": 0.0},
    )

    def _completion(**kwargs):
        captured.update(kwargs)
        return response

    monkeypatch.setattr(provider, "_import_litellm", lambda: types.SimpleNamespace(completion=_completion))

    metadata = provider.generate_with_metadata("查询GMV", tools=_SQL_TOOLS, tool_choice="auto")
    assert captured["tools"] == _SQL_TOOLS
    assert captured["tool_choice"] == "auto"
    assert metadata.content == ""
    assert metadata.tool_calls == [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "execute_sql", "arguments": '{"sql":"SELECT 1"}'},
        }
    ]
    assert metadata.prompt_tokens == 9


def test_litellm_provider_stream_yields_chunks_and_metadata(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    provider = LiteLLMProvider()

    captured: dict = {}

    def _chunk(content, usage=None):
        delta = types.SimpleNamespace(content=content, tool_calls=None)
        return types.SimpleNamespace(id="req-stream", usage=usage, choices=[types.SimpleNamespace(delta=delta)])

    usage = types.SimpleNamespace(prompt_tokens=7, completion_tokens=3, total_tokens=10)
    stream_chunks = [_chunk("SELECT"), _chunk(" 1"), _chunk(None, usage=usage)]

    def _completion(**kwargs):
        captured.update(kwargs)
        return iter(stream_chunks)

    monkeypatch.setattr(provider, "_import_litellm", lambda: types.SimpleNamespace(completion=_completion))

    pieces = list(provider.generate_stream("查询GMV"))
    assert captured["stream"] is True
    assert pieces == ["SELECT", " 1"]
    metadata = provider.last_stream_metadata
    assert metadata is not None
    assert metadata.content == "SELECT 1"
    assert metadata.prompt_tokens == 7
    assert metadata.completion_tokens == 3
    assert metadata.total_tokens == 10
    assert metadata.request_id == "req-stream"


def test_litellm_fallback_openai_compatible_passes_tools(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mimo-v2.5-pro")
    monkeypatch.setattr(settings, "llm_max_retries", 0)

    captured: dict = {}

    class _Response:
        status_code = 200

        def json(self):
            return {
                "id": "req-oc-tools",
                "model": "mimo-v2.5-pro",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-9",
                                    "type": "function",
                                    "function": {"name": "execute_sql", "arguments": '{"sql": "SELECT 1"}'},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            }

    def _post(url, headers, json, timeout):
        captured["json"] = json
        return _Response()

    monkeypatch.setattr("httpx.post", _post)
    provider = LiteLLMProvider(base_url="https://mock-llm.local/v1")

    metadata = provider._generate_openai_compatible("今天GMV多少", 0.0, tools=_SQL_TOOLS, tool_choice="auto")
    assert captured["json"]["tools"] == _SQL_TOOLS
    assert captured["json"]["tool_choice"] == "auto"
    assert metadata.provider == "litellm"
    assert metadata.content == ""
    assert metadata.tool_calls is not None
    assert metadata.tool_calls[0]["function"]["name"] == "execute_sql"


# ---------- OpenAICompatibleProvider: 直连一等公民 ----------


def test_openai_compatible_provider_requires_base_url_and_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_base_url", "")
    with pytest.raises(ProviderConfigError, match="LLM_BASE_URL"):
        OpenAICompatibleProvider()
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key_env", "")
    with pytest.raises(ProviderConfigError, match="LLM_API_KEY"):
        OpenAICompatibleProvider(base_url="https://mock-llm.local/v1")


def test_openai_compatible_provider_success_with_tools_and_usage(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    captured: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "req-oc-1",
                "model": "mock-model",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-2",
                                    "type": "function",
                                    "function": {"name": "execute_sql", "arguments": '{"sql": "SELECT 1"}'},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 6, "total_tokens": 17},
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        transport=httpx.MockTransport(_handler),
    )
    metadata = provider.generate_with_metadata("今天GMV多少", tools=_SQL_TOOLS, tool_choice="auto")

    assert captured["url"] == "https://mock-llm.local/v1/chat/completions"
    assert captured["auth"] == "Bearer demo-key"
    assert captured["body"]["tools"] == _SQL_TOOLS
    assert captured["body"]["tool_choice"] == "auto"
    assert metadata.provider == "openai_compatible"
    assert metadata.model == "mock-model"
    assert metadata.prompt_tokens == 11
    assert metadata.total_tokens == 17
    assert metadata.tool_calls is not None
    assert metadata.tool_calls[0]["id"] == "call-2"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (429, ProviderRateLimitError),
        (500, ProviderResponseError),
    ],
)
def test_openai_compatible_provider_status_error_mapping(monkeypatch, status_code: int, expected):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"code": "ERR", "message": "boom"}})

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        max_retries=0,
        transport=httpx.MockTransport(_handler),
    )
    with pytest.raises(expected):
        provider.generate_with_metadata("hello")


def test_openai_compatible_provider_timeout_maps_typed_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    def _post(*args, **kwargs):
        raise httpx.TimeoutException("connect timed out")

    monkeypatch.setattr("httpx.post", _post)
    provider = OpenAICompatibleProvider(base_url="https://mock-llm.local/v1", max_retries=0)
    with pytest.raises(ProviderTimeoutError):
        provider.generate_with_metadata("hello")


def test_openai_compatible_provider_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    calls = {"count": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500, json={"error": {"code": "ERR", "message": "flaky"}})
        return httpx.Response(
            200,
            json={
                "id": "req-retry",
                "model": "mock-model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        max_retries=1,
        retry_backoff_seconds=0.0,
        transport=httpx.MockTransport(_handler),
    )
    metadata = provider.generate_with_metadata("hello")
    assert calls["count"] == 2
    assert metadata.content == "ok"


def test_openai_compatible_provider_auth_error_not_retried(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    calls = {"count": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": {"code": "AUTH", "message": "bad key"}})

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        max_retries=2,
        retry_backoff_seconds=0.0,
        transport=httpx.MockTransport(_handler),
    )
    with pytest.raises(ProviderAuthError):
        provider.generate_with_metadata("hello")
    assert calls["count"] == 1


def test_openai_compatible_provider_stream_sse_chunks_and_usage(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    captured: dict = {}
    sse_body = (
        'data: {"id":"req-sse-1","model":"mock-model","choices":[{"delta":{"content":"SELECT"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" gmv"}}]}\n\n'
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":6,"completion_tokens":2,"total_tokens":8}}\n\n'
        "data: [DONE]\n\n"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        transport=httpx.MockTransport(_handler),
    )
    chunks = list(provider.generate_stream("今天GMV多少"))
    assert captured["body"]["stream"] is True
    assert chunks == ["SELECT", " gmv"]
    metadata = provider.last_stream_metadata
    assert metadata is not None
    assert metadata.content == "SELECT gmv"
    assert metadata.prompt_tokens == 6
    assert metadata.completion_tokens == 2
    assert metadata.total_tokens == 8
    assert metadata.request_id == "req-sse-1"


def test_openai_compatible_provider_stream_error_status_mapped(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": "RATE", "message": "slow down"}})

    provider = OpenAICompatibleProvider(
        base_url="https://mock-llm.local/v1",
        transport=httpx.MockTransport(_handler),
    )
    with pytest.raises(ProviderRateLimitError):
        list(provider.generate_stream("hello"))


def test_create_provider_openai_compatible(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "demo-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")
    monkeypatch.setattr(settings, "llm_base_url", "https://mock-llm.local/v1")
    provider = create_provider("openai_compatible")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai_compatible"


def test_create_provider_unknown_lists_openai_compatible():
    with pytest.raises(Exception, match="openai_compatible"):
        create_provider("not-exists")


def test_openai_compatible_provider_api_key_env_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key_env", "TEST_OPENAI_COMPAT_KEY")
    monkeypatch.setattr(settings, "llm_model", "mock-model")
    monkeypatch.setenv("TEST_OPENAI_COMPAT_KEY", "env-key")
    provider = OpenAICompatibleProvider(base_url="https://mock-llm.local/v1")
    assert provider._api_key == "env-key"


# ---------- token/成本预估与预算联动 ----------


def test_estimate_prompt_tokens_heuristic():
    assert estimate_prompt_tokens("") == 0
    assert estimate_prompt_tokens("abc") == 1
    assert estimate_prompt_tokens("a" * 12) == 3


def test_estimate_cost_uses_configured_prices(monkeypatch):
    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", True)
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 0.5)
    monkeypatch.setattr(settings, "llm_cost_per_1k_completion_tokens_usd", 1.0)
    monkeypatch.setattr(settings, "llm_estimated_completion_tokens", 100)
    assert estimate_llm_cost_usd(200) == pytest.approx(0.2)
    assert estimate_llm_cost_usd(200, completion_tokens=0) == pytest.approx(0.1)


def test_estimate_cost_disabled_returns_zero(monkeypatch):
    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", False)
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 0.5)
    assert estimate_llm_cost_usd(2000) == 0.0


def test_check_budget_default_prices_keep_allow(monkeypatch):
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 0.0)
    monkeypatch.setattr(settings, "llm_cost_per_1k_completion_tokens_usd", 0.0)
    manager = LLMBudgetManager(enabled=True, soft_limit=0.0, hard_limit=0.05, scope="daily")
    decision = manager.check_budget("nl2sql", "litellm", "m", prompt="今天GMV多少")
    assert decision["allowed"] is True
    assert decision["action"] == "allow"
    assert decision["estimated_cost"] == 0.0


def test_check_budget_blocks_on_prompt_estimate(monkeypatch):
    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", True)
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 1.0)
    monkeypatch.setattr(settings, "llm_cost_per_1k_completion_tokens_usd", 0.0)
    monkeypatch.setattr(settings, "llm_estimated_completion_tokens", 0)
    manager = LLMBudgetManager(enabled=True, soft_limit=0.0, hard_limit=0.05, scope="daily")

    decision = manager.check_budget("nl2sql", "litellm", "m", prompt="a" * 400)
    assert decision["allowed"] is False
    assert decision["action"] == "fallback"
    assert decision["estimated_cost"] == pytest.approx(0.1)

    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", False)
    decision = manager.check_budget("nl2sql", "litellm", "m", prompt="a" * 400)
    assert decision["allowed"] is True
    assert decision["action"] == "allow"


def test_pipeline_budget_blocked_by_prompt_estimate(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.001)
    monkeypatch.setattr(settings, "llm_budget_soft_usd", 0.0)
    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", True)
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 1.0)
    monkeypatch.setattr(settings, "llm_cost_per_1k_completion_tokens_usd", 0.0)
    monkeypatch.setattr(settings, "llm_estimated_completion_tokens", 0)
    reset_runtime_for_test()

    calls = {"count": 0}

    class _CountingProvider(FakeLLMProvider):
        def generate_with_metadata(self, prompt, *, tools=None, tool_choice=None):
            calls["count"] += 1
            return super().generate_with_metadata(prompt, tools=tools, tool_choice=tool_choice)

    monkeypatch.setattr(
        "app.services.nl2sql_pipeline.create_provider",
        lambda *_args, **_kwargs: _CountingProvider(),
    )
    pipeline = NL2SQLPipeline()
    result = pipeline.preview("今天GMV多少", generator="llm", provider="litellm", fallback_to_mock=True)
    assert result["generator_used"] == "mock_fallback"
    assert "budget_blocked" in (result["fallback_reason"] or "")
    assert calls["count"] == 0
    budget_status = result.get("budget_status") or {}
    assert budget_status.get("estimated_cost", 0.0) > 0.0

    assert get_llm_budget_manager().summary()["current_cost"] == 0.0


def test_judge_budget_blocked_by_prompt_estimate(monkeypatch):
    monkeypatch.setattr(settings, "llm_budget_enabled", True)
    monkeypatch.setattr(settings, "llm_budget_hard_usd", 0.001)
    monkeypatch.setattr(settings, "llm_cost_estimation_enabled", True)
    monkeypatch.setattr(settings, "llm_cost_per_1k_prompt_tokens_usd", 1.0)
    monkeypatch.setattr(settings, "llm_cost_per_1k_completion_tokens_usd", 0.0)
    monkeypatch.setattr(settings, "llm_estimated_completion_tokens", 0)
    reset_runtime_for_test()

    judge = LLMJudgeProvider(provider="litellm", fallback_to_fake=True)
    result = judge.evaluate(
        JudgeInput(
            case_id="estimate_case_001",
            query="今天GMV多少",
            expected="success",
            actual="success",
            rubric="",
        )
    )
    assert result.judge_provider == "fallback_fake"
    assert result.fallback_used is True
    assert "budget_blocked" in result.fallback_reason
