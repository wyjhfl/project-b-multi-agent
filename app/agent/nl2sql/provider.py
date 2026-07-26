from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from app.core.config import settings


class UnknownProviderError(ValueError):
    """未知的 LLM Provider 名称。"""


class ProviderConfigError(ValueError):
    """Provider 配置错误（例如缺少 API Key 或模型配置）。"""


class ProviderAuthError(RuntimeError):
    """Provider 认证失败。"""


class ProviderTimeoutError(TimeoutError):
    """Provider 调用超时。"""


class ProviderRateLimitError(RuntimeError):
    """Provider 触发限流。"""


class ProviderModelError(RuntimeError):
    """Provider 模型不可用或模型参数错误。"""


class ProviderResponseError(RuntimeError):
    """Provider 返回结构异常。"""


@dataclass
class LLMGenerateMetadata:
    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    request_id: str
    latency_ms: float
    error_type: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type,
            "tool_calls": self.tool_calls,
        }


def _resolve_llm_api_key(api_key: str | None) -> str:
    """解析 API Key：显式传入 > settings.llm_api_key > llm_api_key_env 指向的环境变量。"""
    if api_key is not None:
        return api_key
    if settings.llm_api_key:
        return settings.llm_api_key
    env_name = settings.llm_api_key_env
    if isinstance(env_name, str) and env_name.strip():
        return os.environ.get(env_name.strip(), "")
    return ""


def _redact_provider_error_detail(detail: str) -> str:
    detail = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "[redacted]", detail)
    detail = re.sub(r"tp-[A-Za-z0-9_\-]{16,}", "[redacted]", detail)
    detail = re.sub(r"(?i)bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted]", detail)
    detail = re.sub(
        r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^&\s]+)",
        r"\1=[redacted]",
        detail,
    )
    detail = re.sub(r"(?i)(https?://[^:/\s]+):[^@\s]+@", r"\1:[redacted]@", detail)
    return detail


def _safe_http_error_detail(response: Any) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        code = str(error.get("code") or error.get("type") or "").strip()
        message = str(error.get("message") or "").strip()
    else:
        code = str(payload.get("code") or "").strip()
        message = str(payload.get("message") or "").strip()
    parts = [item for item in [code, message] if item]
    if not parts:
        return ""
    detail = " | ".join(parts)
    return _redact_provider_error_detail(detail)[:240]


def _raise_for_openai_compatible_status(response: Any) -> None:
    """把 OpenAI-compatible HTTP 状态码映射为类型化异常（401/403/429 等）。"""
    if response.status_code in {401, 403}:
        raise ProviderAuthError(f"OpenAI-compatible endpoint auth failed: {response.status_code}")
    if response.status_code == 429:
        raise ProviderRateLimitError("OpenAI-compatible endpoint rate limited")
    if response.status_code >= 400:
        safe_detail = _safe_http_error_detail(response)
        suffix = f": {safe_detail}" if safe_detail else ""
        raise ProviderResponseError(f"OpenAI-compatible endpoint returned {response.status_code}{suffix}")


def _build_openai_chat_body(
    *,
    model: str,
    prompt: str,
    temperature: float,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """构造 OpenAI /chat/completions 请求体，按需附加 tools/tool_choice/stream。"""
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice
    if stream:
        body["stream"] = True
    return body


def _normalize_tool_calls(raw: Any) -> list[dict[str, Any]] | None:
    """统一 tool_calls 为 OpenAI dict 结构，兼容 dict 与对象属性两种形态。"""
    if not raw:
        return None
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = str(function.get("name") or "")
            arguments = function.get("arguments")
            call_id = str(item.get("id") or "")
        else:
            function = getattr(item, "function", None)
            name = str(getattr(function, "name", "") or "")
            arguments = getattr(function, "arguments", None)
            call_id = str(getattr(item, "id", "") or "")
        if arguments is None:
            arguments = ""
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        normalized.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    return normalized or None


def _merge_stream_tool_call_fragment(acc: dict[int, dict[str, Any]], fragments: Any) -> None:
    """合并流式 tool_calls 增量：同 index 的 id/name 取首个非空值，arguments 逐段拼接。"""
    if not fragments:
        return
    for fragment in fragments:
        if isinstance(fragment, dict):
            index = int(fragment.get("index", 0) or 0)
            call_id = str(fragment.get("id") or "")
            function = fragment.get("function") if isinstance(fragment.get("function"), dict) else {}
            name = str(function.get("name") or "")
            arguments = function.get("arguments")
        else:
            index = int(getattr(fragment, "index", 0) or 0)
            call_id = str(getattr(fragment, "id", "") or "")
            function = getattr(fragment, "function", None)
            name = str(getattr(function, "name", "") or "")
            arguments = getattr(function, "arguments", None)
        slot = acc.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if call_id and not slot["id"]:
            slot["id"] = call_id
        if name and not slot["function"]["name"]:
            slot["function"]["name"] = name
        if arguments:
            slot["function"]["arguments"] += str(arguments)


def _finalize_stream_tool_calls(acc: dict[int, dict[str, Any]]) -> list[dict[str, Any]] | None:
    if not acc:
        return None
    return [acc[index] for index in sorted(acc)]


def _parse_openai_chat_payload(
    payload: Any,
    *,
    provider_name: str,
    fallback_model: str,
    started: float,
) -> LLMGenerateMetadata:
    """解析 OpenAI /chat/completions 响应，容忍 content 为空但携带 tool_calls 的场景。"""
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices:
        raise ProviderResponseError("OpenAI-compatible endpoint response missing choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    tool_calls = _normalize_tool_calls(message.get("tool_calls") if isinstance(message, dict) else None)
    if content is None and not tool_calls:
        raise ProviderResponseError("OpenAI-compatible endpoint response missing message.content")

    usage = payload.get("usage") if isinstance(payload, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

    return LLMGenerateMetadata(
        content="" if content is None else str(content),
        provider=provider_name,
        model=str(payload.get("model") or fallback_model),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost=0.0,
        request_id=str(payload.get("id") or ""),
        latency_ms=(time.perf_counter() - started) * 1000.0,
        error_type=None,
        tool_calls=tool_calls,
    )


def _stream_openai_compatible_chat(
    *,
    provider_name: str,
    api_key: str,
    model: str,
    base_url: str,
    timeout_seconds: float,
    temperature: float,
    prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any | None,
    started: float,
    on_metadata: Callable[[LLMGenerateMetadata], None],
    transport: Any | None = None,
) -> Iterator[str]:
    """OpenAI-compatible SSE 流式调用：逐行解析 data: 增量并产出文本 chunk。

    usage 依赖服务端在流末尾的 chunk 返回（部分实现不返回，此时记 0），
    迭代结束后通过 on_metadata 回传完整元数据。
    """
    try:
        import httpx
    except ImportError as exc:
        raise ProviderConfigError("OpenAI-compatible 直连需要 httpx。") from exc

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = _build_openai_chat_body(
        model=model,
        prompt=prompt,
        temperature=temperature,
        tools=tools,
        tool_choice=tool_choice,
        stream=True,
    )

    parts: list[str] = []
    tool_call_acc: dict[int, dict[str, Any]] = {}
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    request_id = ""
    model_name = model

    client_kwargs: dict[str, Any] = {"timeout": timeout_seconds}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        with httpx.Client(**client_kwargs) as client:
            with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code >= 400:
                    response.read()
                    _raise_for_openai_compatible_status(response)
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("id"):
                        request_id = str(event["id"])
                    if event.get("model"):
                        model_name = str(event["model"])
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
                    choices = event.get("choices") or []
                    if not choices or not isinstance(choices[0], dict):
                        continue
                    delta = choices[0].get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    piece = delta.get("content")
                    if piece:
                        parts.append(str(piece))
                        yield str(piece)
                    _merge_stream_tool_call_fragment(tool_call_acc, delta.get("tool_calls"))
    except httpx.TimeoutException as exc:
        raise ProviderTimeoutError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise ProviderResponseError(str(exc)) from exc

    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    on_metadata(
        LLMGenerateMetadata(
            content="".join(parts),
            provider=provider_name,
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=0.0,
            request_id=request_id,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_type=None,
            tool_calls=_finalize_stream_tool_calls(tool_call_acc),
        )
    )


class LLMProvider(ABC):
    """LLM Provider 抽象基类。"""

    _last_stream_metadata: LLMGenerateMetadata | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称标识。"""
        ...

    def generate(self, prompt: str) -> str:
        """兼容旧接口：返回纯文本内容。"""
        ...

    def generate_with_metadata(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> LLMGenerateMetadata:
        """结构化返回：内容 + token/cost/延迟等元数据。

        tools 为 OpenAI 格式（JSON Schema）工具列表；默认实现不支持工具调用，忽略之。
        """
        started = time.perf_counter()
        content = self.generate(prompt)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return LLMGenerateMetadata(
            content=content,
            provider=self.name,
            model="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            request_id="",
            latency_ms=latency_ms,
            error_type=None,
        )

    @property
    def last_stream_metadata(self) -> LLMGenerateMetadata | None:
        """最近一次 generate_stream 的完整元数据（迭代结束后可读取）。"""
        return self._last_stream_metadata

    def generate_stream(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> Iterator[str]:
        """流式生成：产出文本增量 chunk。

        默认实现复用一次性结果并按 llm_stream_chunk_chars 切块模拟增量输出，
        完整元数据在迭代结束后通过 last_stream_metadata 获取。
        """
        if tools is None and tool_choice is None:
            metadata = self.generate_with_metadata(prompt)
        else:
            metadata = self.generate_with_metadata(prompt, tools=tools, tool_choice=tool_choice)
        self._last_stream_metadata = metadata
        chunk_chars = max(1, int(settings.llm_stream_chunk_chars))
        content = metadata.content or ""
        for start in range(0, len(content), chunk_chars):
            yield content[start : start + chunk_chars]


class FakeLLMProvider(LLMProvider):
    """Fake Provider：离线可跑，不依赖外网。"""

    @property
    def name(self) -> str:
        return "fake"

    RESPONSE_MAP: list[dict[str, Any]] = [
        {
            "keywords": ["GMV", "gmv", "销售额"],
            "response": {
                "sql": "SELECT metric_date, gmv, order_count FROM daily_metrics WHERE metric_date = '2024-01-15'",
                "confidence": 0.9,
                "reasoning": "根据关键词匹配到 GMV 查询",
                "selected_tables": ["daily_metrics"],
            },
        },
        {
            "keywords": ["新增用户", "用户"],
            "response": {
                "sql": "SELECT COUNT(*) as new_users FROM users WHERE registered_date LIKE '2024-01%'",
                "confidence": 0.85,
                "reasoning": "根据关键词匹配到新增用户查询",
                "selected_tables": ["users"],
            },
        },
        {
            "keywords": ["订单", "订单量"],
            "response": {
                "sql": "SELECT COUNT(*) as order_count FROM orders WHERE order_date = '2024-01-15'",
                "confidence": 0.85,
                "reasoning": "根据关键词匹配到订单查询",
                "selected_tables": ["orders"],
            },
        },
        {
            "keywords": ["商品", "Top商品", "热销", "热门商品", "top商品"],
            "response": {
                "sql": "SELECT p.name, p.category, SUM(o.quantity) as total_qty FROM orders o JOIN products p ON o.product_id = p.id WHERE o.status = 'completed' GROUP BY o.product_id ORDER BY total_qty DESC LIMIT 5",
                "confidence": 0.8,
                "reasoning": "根据关键词匹配到商品排名查询",
                "selected_tables": ["products", "orders"],
            },
        },
        {
            "keywords": ["退款", "退款率"],
            "response": {
                "sql": "SELECT (SELECT COUNT(*) FROM refund_orders) * 100.0 / (SELECT COUNT(*) FROM orders) as refund_rate_percent",
                "confidence": 0.8,
                "reasoning": "根据关键词匹配到退款率查询",
                "selected_tables": ["refund_orders", "orders"],
            },
        },
    ]

    TOOL_NAME_PRIORITY: tuple[str, ...] = ("execute_sql", "run_sql", "query_database")

    def generate(self, prompt: str) -> str:
        return self.generate_with_metadata(prompt).content

    def generate_with_metadata(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> LLMGenerateMetadata:
        started = time.perf_counter()
        payload: dict[str, Any] | None = None
        for entry in self.RESPONSE_MAP:
            if any(kw in prompt for kw in entry["keywords"]):
                payload = entry["response"]
                break
        matched = payload is not None

        if payload is None:
            payload = {
                "sql": "",
                "confidence": 0.0,
                "reasoning": "无法识别查询",
                "selected_tables": [],
            }

        content = json.dumps(payload, ensure_ascii=False)
        tool_calls = self._build_tool_calls(payload, matched, tools, tool_choice)
        if tool_calls:
            content = ""

        latency_ms = (time.perf_counter() - started) * 1000.0
        return LLMGenerateMetadata(
            content=content,
            provider=self.name,
            model="fake-offline",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            request_id="fake-request",
            latency_ms=latency_ms,
            error_type=None,
            tool_calls=tool_calls,
        )

    def _build_tool_calls(
        self,
        payload: dict[str, Any],
        matched: bool,
        tools: list[dict[str, Any]] | None,
        tool_choice: Any | None,
    ) -> list[dict[str, Any]] | None:
        """确定性工具调用：tool_choice 强制指定必调用；否则关键词命中才调用。"""
        if not tools or tool_choice == "none":
            return None
        forced_name = ""
        if isinstance(tool_choice, dict):
            function = tool_choice.get("function")
            forced_name = str((function or {}).get("name") or "").strip()
        if not forced_name and not matched:
            return None
        tool_name = forced_name or self._select_tool_name(tools)
        if not tool_name:
            return None
        arguments = json.dumps({"sql": str(payload.get("sql", ""))}, ensure_ascii=False)
        return [
            {
                "id": "fake-tool-call-1",
                "type": "function",
                "function": {"name": tool_name, "arguments": arguments},
            }
        ]

    def _select_tool_name(self, tools: list[dict[str, Any]]) -> str:
        names: list[str] = []
        for tool in tools:
            function = tool.get("function") if isinstance(tool, dict) else None
            name = str((function or {}).get("name") or "").strip()
            if name:
                names.append(name)
        for preferred in self.TOOL_NAME_PRIORITY:
            if preferred in names:
                return preferred
        return names[0] if names else ""


class LiteLLMProvider(LLMProvider):
    """LiteLLM Provider：可选真实调用，默认不启用。"""

    @property
    def name(self) -> str:
        return "litellm"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        temperature: float | None = None,
    ) -> None:
        self._api_key = _resolve_llm_api_key(api_key)
        self._model = model or settings.llm_model or "gpt-3.5-turbo"
        self._base_url = (settings.llm_base_url if base_url is None else (base_url or "")).strip()
        self._timeout_seconds = max(1.0, float(settings.llm_timeout_seconds if timeout_seconds is None else timeout_seconds))
        self._max_retries = max(0, int(settings.llm_max_retries if max_retries is None else max_retries))
        self._retry_backoff_seconds = max(
            0.0,
            float(settings.llm_retry_backoff_seconds if retry_backoff_seconds is None else retry_backoff_seconds),
        )
        self._temperature = float(settings.llm_temperature if temperature is None else temperature)

        if not self._api_key:
            raise ProviderConfigError("LiteLLMProvider 需要 LLM_API_KEY 配置，当前为空。")

    def _litellm_model_name(self) -> str:
        if self._base_url and "/" not in self._model:
            return f"openai/{self._model}"
        return self._model

    def _build_completion_payload(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._litellm_model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
            "temperature": self._temperature,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if stream:
            payload["stream"] = True
        if self._base_url:
            payload["api_base"] = self._base_url
        return payload

    def generate(self, prompt: str) -> str:
        return self.generate_with_metadata(prompt).content

    def generate_with_metadata(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> LLMGenerateMetadata:
        litellm = self._import_litellm()
        started = time.perf_counter()
        attempt = 0
        last_error: Exception | None = None
        while attempt <= self._max_retries:
            try:
                payload = self._build_completion_payload(prompt, tools=tools, tool_choice=tool_choice)
                response = litellm.completion(**payload)
                return self._normalize_response(response, started)
            except Exception as exc:
                mapped = self._map_exception(exc)
                if self._base_url and isinstance(mapped, ProviderResponseError):
                    return self._generate_openai_compatible(prompt, started, tools=tools, tool_choice=tool_choice)
                last_error = mapped
                if attempt >= self._max_retries:
                    raise mapped
                attempt += 1
                if self._retry_backoff_seconds > 0:
                    time.sleep(self._retry_backoff_seconds)

        if last_error is None:
            raise ProviderResponseError("LiteLLMProvider 未知异常。")
        raise last_error

    def generate_stream(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> Iterator[str]:
        """流式生成：litellm stream=True 逐块产出文本增量。

        建流阶段沿用重试与 openai_compatible 兜底；一旦开始产出 chunk，
        异常直接映射抛出不再重试。usage 以携带 usage 的 chunk 为准，缺失时记 0。
        """
        litellm = self._import_litellm()
        started = time.perf_counter()
        attempt = 0
        stream = None
        while stream is None:
            try:
                payload = self._build_completion_payload(prompt, tools=tools, tool_choice=tool_choice, stream=True)
                stream = litellm.completion(**payload)
            except Exception as exc:
                mapped = self._map_exception(exc)
                if self._base_url and isinstance(mapped, ProviderResponseError):
                    yield from self._stream_openai_compatible(prompt, started, tools=tools, tool_choice=tool_choice)
                    return
                if attempt >= self._max_retries:
                    raise mapped
                attempt += 1
                if self._retry_backoff_seconds > 0:
                    time.sleep(self._retry_backoff_seconds)

        parts: list[str] = []
        tool_call_acc: dict[int, dict[str, Any]] = {}
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        request_id = ""
        try:
            for chunk in stream:
                chunk_id = getattr(chunk, "id", "")
                if chunk_id:
                    request_id = str(chunk_id)
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue
                piece = getattr(delta, "content", None)
                if piece:
                    parts.append(str(piece))
                    yield str(piece)
                _merge_stream_tool_call_fragment(tool_call_acc, getattr(delta, "tool_calls", None))
        except Exception as exc:
            raise self._map_exception(exc)

        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        self._last_stream_metadata = LLMGenerateMetadata(
            content="".join(parts),
            provider=self.name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=0.0,
            request_id=request_id,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_type=None,
            tool_calls=_finalize_stream_tool_calls(tool_call_acc),
        )

    def _generate_openai_compatible(
        self,
        prompt: str,
        started: float,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> LLMGenerateMetadata:
        try:
            import httpx
        except ImportError as exc:
            raise ProviderConfigError("OpenAI-compatible fallback 需要 httpx。") from exc

        url = self._base_url.rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=_build_openai_chat_body(
                    model=self._model,
                    prompt=prompt,
                    temperature=self._temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                ),
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError(str(exc)) from exc

        _raise_for_openai_compatible_status(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("OpenAI-compatible endpoint returned non-json response") from exc

        return _parse_openai_chat_payload(
            payload,
            provider_name=self.name,
            fallback_model=self._model,
            started=started,
        )

    def _stream_openai_compatible(
        self,
        prompt: str,
        started: float,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> Iterator[str]:
        def _on_metadata(metadata: LLMGenerateMetadata) -> None:
            self._last_stream_metadata = metadata

        yield from _stream_openai_compatible_chat(
            provider_name=self.name,
            api_key=self._api_key,
            model=self._model,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
            temperature=self._temperature,
            prompt=prompt,
            tools=tools,
            tool_choice=tool_choice,
            started=started,
            on_metadata=_on_metadata,
        )

    def _import_litellm(self):
        try:
            import litellm
        except ImportError as exc:
            raise ProviderConfigError(
                "使用 LiteLLMProvider 需要安装 litellm，请执行: pip install litellm"
            ) from exc
        return litellm

    def _normalize_response(self, response: Any, started: float) -> LLMGenerateMetadata:
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        cost = float(getattr(response, "_hidden_params", {}).get("response_cost", 0.0) or 0.0)
        request_id = str(getattr(response, "id", ""))

        choices = getattr(response, "choices", None)
        if not choices:
            raise ProviderResponseError("LiteLLM 返回缺少 choices。")

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message is not None else None
        tool_calls = _normalize_tool_calls(getattr(message, "tool_calls", None) if message is not None else None)
        if content is None and not tool_calls:
            raise ProviderResponseError("LiteLLM 返回缺少 message.content。")

        latency_ms = (time.perf_counter() - started) * 1000.0
        return LLMGenerateMetadata(
            content="" if content is None else str(content),
            provider=self.name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            request_id=request_id,
            latency_ms=latency_ms,
            error_type=None,
            tool_calls=tool_calls,
        )

    def _map_exception(self, exc: Exception) -> Exception:
        text = str(exc).lower()
        name = exc.__class__.__name__.lower()
        if "auth" in text or "authentication" in text or "permission" in text:
            return ProviderAuthError(str(exc))
        if "timeout" in text or "timed out" in text or "timeouterror" in name:
            return ProviderTimeoutError(str(exc))
        if "rate limit" in text or "ratelimit" in name or "429" in text:
            return ProviderRateLimitError(str(exc))
        if "model" in text or "not found" in text:
            return ProviderModelError(str(exc))
        return ProviderResponseError(str(exc))


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible Provider：纯 httpx 直连 /chat/completions，无需安装 litellm。"""

    RETRYABLE_ERRORS = (ProviderTimeoutError, ProviderRateLimitError, ProviderResponseError)

    @property
    def name(self) -> str:
        return "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        temperature: float | None = None,
        transport: Any | None = None,
    ) -> None:
        self._api_key = _resolve_llm_api_key(api_key)
        self._model = model or settings.llm_model or "gpt-3.5-turbo"
        self._base_url = (settings.llm_base_url if base_url is None else (base_url or "")).strip()
        self._timeout_seconds = max(1.0, float(settings.llm_timeout_seconds if timeout_seconds is None else timeout_seconds))
        self._max_retries = max(0, int(settings.llm_max_retries if max_retries is None else max_retries))
        self._retry_backoff_seconds = max(
            0.0,
            float(settings.llm_retry_backoff_seconds if retry_backoff_seconds is None else retry_backoff_seconds),
        )
        self._temperature = float(settings.llm_temperature if temperature is None else temperature)
        self._transport = transport

        if not self._base_url:
            raise ProviderConfigError("OpenAICompatibleProvider 需要 LLM_BASE_URL 配置，当前为空。")
        if not self._api_key:
            raise ProviderConfigError("OpenAICompatibleProvider 需要 LLM_API_KEY 配置，当前为空。")

    def generate(self, prompt: str) -> str:
        return self.generate_with_metadata(prompt).content

    def generate_with_metadata(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> LLMGenerateMetadata:
        """一次性生成：仅对超时/限流/响应异常重试，认证与模型错误快速失败。"""
        started = time.perf_counter()
        attempt = 0
        while True:
            try:
                return self._request_once(prompt, started, tools=tools, tool_choice=tool_choice)
            except self.RETRYABLE_ERRORS:
                if attempt >= self._max_retries:
                    raise
                attempt += 1
                if self._retry_backoff_seconds > 0:
                    time.sleep(self._retry_backoff_seconds)

    def _request_once(
        self,
        prompt: str,
        started: float,
        *,
        tools: list[dict[str, Any]] | None,
        tool_choice: Any | None,
    ) -> LLMGenerateMetadata:
        try:
            import httpx
        except ImportError as exc:
            raise ProviderConfigError("OpenAICompatibleProvider 需要 httpx。") from exc

        url = self._base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = _build_openai_chat_body(
            model=self._model,
            prompt=prompt,
            temperature=self._temperature,
            tools=tools,
            tool_choice=tool_choice,
        )
        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport, timeout=self._timeout_seconds) as client:
                    response = client.post(url, headers=headers, json=body)
            else:
                response = httpx.post(url, headers=headers, json=body, timeout=self._timeout_seconds)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError(str(exc)) from exc

        _raise_for_openai_compatible_status(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("OpenAI-compatible endpoint returned non-json response") from exc

        return _parse_openai_chat_payload(
            payload,
            provider_name=self.name,
            fallback_model=self._model,
            started=started,
        )

    def generate_stream(
        self,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> Iterator[str]:
        """SSE 流式：逐行解析 data: 增量产出 chunk，元数据迭代结束后可读取。"""
        started = time.perf_counter()

        def _on_metadata(metadata: LLMGenerateMetadata) -> None:
            self._last_stream_metadata = metadata

        yield from _stream_openai_compatible_chat(
            provider_name=self.name,
            api_key=self._api_key,
            model=self._model,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
            temperature=self._temperature,
            prompt=prompt,
            tools=tools,
            tool_choice=tool_choice,
            started=started,
            on_metadata=_on_metadata,
            transport=self._transport,
        )


def create_provider(
    provider_name: str | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
    temperature: float | None = None,
) -> LLMProvider:
    """根据配置创建 LLM Provider。"""
    name = provider_name or settings.llm_provider
    if name == "fake":
        return FakeLLMProvider()
    if name == "litellm":
        return LiteLLMProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            temperature=temperature,
        )
    if name == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            temperature=temperature,
        )
    raise UnknownProviderError(f"未知的 LLM Provider: {name!r}，支持: fake, litellm, openai_compatible (unknown provider)")
