from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = ROOT_DIR / "docs" / "production_landing_operator_runbook_v47.md"


def test_production_landing_operator_runbook_documents_failure_and_safe_next_steps() -> None:
    text = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "production_landing_status.py" in text
    assert "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1" in text
    assert "production_landing_env_check.py" in text
    assert "production_landing_execution_gate.py" in text
    assert "production_landing_env_runner.py --action local-infra-mcp-smoke" in text
    assert "production_landing_env_runner.py --action local-business-smoke" in text
    assert "production_landing_env_runner.py --action business-smoke" in text
    assert "business_system_read_smoke.ps1 -EnvPath local\\production_landing.staging.env" in text
    assert "local_business_mock_used=true" in text
    assert "localhost" in text
    assert "不再自动判为 local mock" in text
    assert "BUSINESS_SYSTEM_NAME=local_business_read_mock" in text
    assert "real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "XIAOMI_LLM_API_KEY" in text
    assert "Read-Host -AsSecureString" in text


def test_production_landing_operator_runbook_does_not_contain_plaintext_secret() -> None:
    text = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "tp-" not in text
