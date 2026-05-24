from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


class UnknownProviderError(ValueError):
    """未知 LLM Provider 名称"""


class ProviderConfigError(ValueError):
    """LLM Provider 配置错误（如缺少 API Key）"""


class LLMProvider(ABC):
    """LLM Provider 抽象基类

    定义 generate 接口，所有 LLM provider 必须实现。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称标识"""
        ...

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """根据 prompt 生成文本

        Args:
            prompt: 输入 prompt

        Returns:
            生成的文本
        """
        ...


class FakeLLMProvider(LLMProvider):
    """Fake LLM Provider

    用于测试，不依赖网络。根据 prompt 中的关键词返回确定性 JSON。
    """

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
        for entry in self.RESPONSE_MAP:
            for kw in entry["keywords"]:
                if kw in prompt:
                    return json.dumps(entry["response"], ensure_ascii=False)

        return json.dumps({
            "sql": "",
            "confidence": 0.0,
            "reasoning": "无法识别查询",
            "selected_tables": [],
        }, ensure_ascii=False)


class LiteLLMProvider(LLMProvider):
    """LiteLLM Provider

    通过 litellm 库调用真实 LLM。需要 API Key。
    测试中不调用此 provider。
    """

    @property
    def name(self) -> str:
        return "litellm"

    def __init__(self) -> None:
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model
        self._provider = settings.llm_provider

        if not self._api_key:
            raise ProviderConfigError("LiteLLMProvider 需要 LLM_API_KEY 配置，当前为空")

    def generate(self, prompt: str) -> str:
        try:
            import litellm
        except ImportError:
            raise ImportError("使用 LiteLLMProvider 需要安装 litellm: pip install litellm")

        model = self._model or "gpt-3.5-turbo"

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
        )

        return response.choices[0].message.content or ""


def create_provider(provider_name: str | None = None) -> LLMProvider:
    """工厂函数：根据配置创建 LLM Provider

    Args:
        provider_name: provider 名称，None 则从配置读取

    Returns:
        LLMProvider 实例

    Raises:
        UnknownProviderError: 未知 provider 名称
        ProviderConfigError: provider 配置错误（如缺少 API Key）
    """
    name = provider_name or settings.llm_provider

    if name == "fake":
        return FakeLLMProvider()
    elif name == "litellm":
        return LiteLLMProvider()
    else:
        raise UnknownProviderError(f"未知的 LLM Provider: {name!r}，支持: fake, litellm")
