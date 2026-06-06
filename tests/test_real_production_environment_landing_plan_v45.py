from __future__ import annotations

from pathlib import Path


PLAN_PATH = Path("docs/v4_5_real_production_environment_landing_plan.md")
MOJIBAKE_MARKERS = ("鐪", "榛", "涓嶆", "浠讳", "銆?", "€?")


def test_real_production_environment_landing_plan_exists_and_covers_real_domains() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")

    assert "真实 LLM" in text
    assert "PostgreSQL" in text
    assert "Redis" in text
    assert "真实 MCP Server" in text
    assert "生产试点环境" in text
    assert "真实业务系统只读 smoke" in text
    assert "public_production_direct_launch" in text
    assert "No-Go" in text


def test_real_production_environment_landing_plan_includes_staging_smoke_commands() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")

    assert "python scripts/real_integration_staging_smoke.py --execute --domains real_llm" in text
    assert "python scripts/real_integration_staging_smoke.py --execute --domains postgres" in text
    assert "python scripts/real_integration_staging_smoke.py --execute --domains redis" in text
    assert "python scripts/real_integration_staging_smoke.py --execute --domains external_mcp" in text
    assert (
        "python scripts/real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp"
        in text
    )


def test_real_production_environment_landing_plan_preserves_safety_boundaries() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")

    assert "默认 fake/offline 路径" in text
    assert "secret 不输出原文" in text
    assert "不读取 key value" in text
    assert "secret_plaintext_output=false" in text
    assert "不宣称公网生产直上" in text
    assert "人工 Go/No-Go" in text
    assert "默认 pytest/CI 不触发真实外部依赖" in text
    assert not any(marker in text for marker in MOJIBAKE_MARKERS)
