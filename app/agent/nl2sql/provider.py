from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

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
        }


class LLMProvider(ABC):
    """LLM Provider 抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称标识。"""
        ...

    def generate(self, prompt: str) -> str:
        """兼容旧接口：返回纯文本内容。"""
        ...

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        """结构化返回：内容 + token/cost/延迟等元数据。"""
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

    def generate(self, prompt: str) -> str:
        return self.generate_with_metadata(prompt).content

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        started = time.perf_counter()
        payload: dict[str, Any] | None = None
        for entry in self.RESPONSE_MAP:
            if any(kw in prompt for kw in entry["keywords"]):
                payload = entry["response"]
                break

        if payload is None:
            payload = {
                "sql": "",
                "confidence": 0.0,
                "reasoning": "无法识别查询",
                "selected_tables": [],
            }

        latency_ms = (time.perf_counter() - started) * 1000.0
        return LLMGenerateMetadata(
            content=json.dumps(payload, ensure_ascii=False),
            provider=self.name,
            model="fake-offline",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            request_id="fake-request",
            latency_ms=latency_ms,
            error_type=None,
        )


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
        self._api_key = settings.llm_api_key if api_key is None else api_key
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

    def generate(self, prompt: str) -> str:
        return self.generate_with_metadata(prompt).content

    def generate_with_metadata(self, prompt: str) -> LLMGenerateMetadata:
        litellm = self._import_litellm()
        started = time.perf_counter()
        attempt = 0
        last_error: Exception | None = None
        while attempt <= self._max_retries:
            try:
                payload: dict[str, Any] = {
                    "model": self._litellm_model_name(),
                    "messages": [{"role": "user", "content": prompt}],
                    "api_key": self._api_key,
                    "timeout": self._timeout_seconds,
                    "temperature": self._temperature,
                }
                if self._base_url:
                    payload["api_base"] = self._base_url
                response = litellm.completion(**payload)
                return self._normalize_response(response, started)
            except Exception as exc:
                mapped = self._map_exception(exc)
                if self._base_url and isinstance(mapped, ProviderResponseError):
                    return self._generate_openai_compatible(prompt, started)
                last_error = mapped
                if attempt >= self._max_retries:
                    raise mapped
                attempt += 1
                if self._retry_backoff_seconds > 0:
                    time.sleep(self._retry_backoff_seconds)

        if last_error is None:
            raise ProviderResponseError("LiteLLMProvider 未知异常。")
        raise last_error

    def _generate_openai_compatible(self, prompt: str, started: float) -> LLMGenerateMetadata:
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
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self._temperature,
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError(str(exc)) from exc

        if response.status_code in {401, 403}:
            raise ProviderAuthError(f"OpenAI-compatible endpoint auth failed: {response.status_code}")
        if response.status_code == 429:
            raise ProviderRateLimitError("OpenAI-compatible endpoint rate limited")
        if response.status_code >= 400:
            safe_detail = self._safe_http_error_detail(response)
            suffix = f": {safe_detail}" if safe_detail else ""
            raise ProviderResponseError(f"OpenAI-compatible endpoint returned {response.status_code}{suffix}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("OpenAI-compatible endpoint returned non-json response") from exc

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not choices:
            raise ProviderResponseError("OpenAI-compatible endpoint response missing choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if content is None:
            raise ProviderResponseError("OpenAI-compatible endpoint response missing message.content")

        usage = payload.get("usage") if isinstance(payload, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

        return LLMGenerateMetadata(
            content=str(content),
            provider=self.name,
            model=str(payload.get("model") or self._model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=0.0,
            request_id=str(payload.get("id") or ""),
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_type=None,
        )

    def _safe_http_error_detail(self, response: Any) -> str:
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
        return self._redact_provider_error_detail(detail)[:240]

    def _redact_provider_error_detail(self, detail: str) -> str:
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
        if content is None:
            raise ProviderResponseError("LiteLLM 返回缺少 message.content。")

        latency_ms = (time.perf_counter() - started) * 1000.0
        return LLMGenerateMetadata(
            content=str(content),
            provider=self.name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            request_id=request_id,
            latency_ms=latency_ms,
            error_type=None,
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
    raise UnknownProviderError(f"未知的 LLM Provider: {name!r}，支持: fake, litellm (unknown provider)")
