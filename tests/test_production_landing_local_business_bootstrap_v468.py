from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_local_business_bootstrap import build_production_landing_local_business_bootstrap


def test_local_business_bootstrap_writes_read_only_mock_config_without_summary_leak(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_local_business_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert summary["env_file_present"] is True
    assert summary["base_url_configured"] is True
    assert summary["token_configured"] is True
    assert summary["read_only"] is True
    assert summary["write_enabled"] is False
    assert summary["tool_allowlist"] == ["business_read_probe"]
    assert "BUSINESS_INTEGRATION_ENABLED=true" in env_text
    assert "BUSINESS_INTEGRATION_READ_ONLY=true" in env_text
    assert "BUSINESS_INTEGRATION_WRITE_ENABLED=false" in env_text
    assert "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL" in env_text
    assert "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN" in env_text
    assert "BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8765" in env_text
    assert "BUSINESS_SYSTEM_TOKEN=local-business-read-token" in env_text
    assert "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe" in env_text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization" in env_text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer" in env_text
    assert "http://127.0.0.1:8765" not in summary_text
    assert "local-business-read-token" not in summary_text
    assert summary["secret_plaintext_output"] is False
