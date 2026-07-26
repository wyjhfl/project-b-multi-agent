"""LLM 返回 JSON 的容错解析回归测试。

真实试点（agnes-2.0-flash, 2026-07-26）暴露的 bad case：模型把合法 JSON
包在 ```json 围栏里，导致 invalid_json 全量降级 mock（fallback_rate=1.0）。
本文件锁定三级容错解析：原样 -> 剥离围栏 -> 提取首尾大括号。
"""
from __future__ import annotations

import json

from app.agent.nl2sql.llm_generator import LLMNL2SQLGenerator
from app.agent.nl2sql.metadata import SchemaMetadataExtractor
from app.agent.nl2sql.provider import LLMGenerateMetadata, LLMProvider


PAYLOAD = {
    "sql": "SELECT metric_date, gmv FROM daily_metrics ORDER BY metric_date DESC LIMIT 7",
    "confidence": 0.9,
    "reasoning": "按日期倒序取最近 7 天 GMV。",
    "selected_tables": ["daily_metrics"],
}


class _StubProvider(LLMProvider):
    """返回固定文本的桩 provider。"""

    def __init__(self, content: str) -> None:
        self._content = content

    @property
    def name(self) -> str:
        return "stub"

    def generate_with_metadata(self, prompt: str, **kwargs) -> LLMGenerateMetadata:
        return LLMGenerateMetadata(
            content=self._content,
            provider="stub",
            model="stub-model",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            request_id="req-stub",
            latency_ms=1.0,
        )


def _schema():
    return SchemaMetadataExtractor().extract()


def _generate(content: str):
    generator = LLMNL2SQLGenerator(provider=_StubProvider(content), fallback_to_mock=True)
    return generator.generate("最近7天GMV", _schema())


def test_plain_json_still_parsed_without_warning():
    result = _generate(json.dumps(PAYLOAD, ensure_ascii=False))
    assert result.generator_used == "llm"
    assert result.fallback_used is False
    assert "围栏" not in " ".join(result.warnings)


def test_fenced_json_with_language_tag_parsed():
    content = "```json\n" + json.dumps(PAYLOAD, ensure_ascii=False) + "\n```"
    result = _generate(content)
    assert result.generator_used == "llm"
    assert result.fallback_used is False
    assert result.sql == PAYLOAD["sql"]
    assert any("围栏" in w for w in result.warnings)


def test_fenced_json_without_language_tag_parsed():
    content = "```\n" + json.dumps(PAYLOAD, ensure_ascii=False) + "\n```"
    result = _generate(content)
    assert result.generator_used == "llm"
    assert result.fallback_used is False


def test_json_wrapped_in_prose_parsed():
    content = "好的，SQL 如下：\n" + json.dumps(PAYLOAD, ensure_ascii=False) + "\n以上供参考。"
    result = _generate(content)
    assert result.generator_used == "llm"
    assert result.fallback_used is False
    assert any("前后缀" in w for w in result.warnings)


def test_garbage_still_falls_back_to_mock():
    result = _generate("完全不是 JSON 的回复")
    assert result.generator_used == "mock_fallback"
    assert result.fallback_used is True
    assert result.fallback_reason.startswith("invalid_json:")
