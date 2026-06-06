from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_xiaomi_llm_bootstrap import build_production_landing_xiaomi_llm_bootstrap


def test_xiaomi_llm_bootstrap_writes_config_and_placeholder_without_key_leak(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XIAOMI_LLM_API_KEY", raising=False)
    env_path = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_xiaomi_llm_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert summary["process_api_key_present"] is False
    assert summary["local_api_key_present_after"] is False
    assert "REAL_LLM_MODEL=mimo-v2.5-pro" in env_text
    assert "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1" in env_text
    assert "REAL_LLM_API_KEY_ENV=XIAOMI_LLM_API_KEY" in env_text
    assert "XIAOMI_LLM_API_KEY=<secret-managed-token>" in env_text
    assert "<secret-managed-token>" not in summary_text
    assert summary["secret_plaintext_output"] is False


def test_xiaomi_llm_bootstrap_copies_process_key_without_summary_leak(tmp_path: Path, monkeypatch) -> None:
    fake_key = "tp-" + "local-real-secret-not-output"
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", fake_key)
    env_path = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_xiaomi_llm_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert summary["process_api_key_present"] is True
    assert summary["api_key_copied_from_process_env"] is True
    assert summary["local_api_key_present_after"] is True
    assert f"XIAOMI_LLM_API_KEY={fake_key}" in env_text
    assert fake_key not in summary_text
    assert summary["secret_plaintext_output"] is False


def test_xiaomi_llm_bootstrap_preserves_existing_local_key_by_default(tmp_path: Path, monkeypatch) -> None:
    fake_existing = "tp-" + "existing-secret-not-output"
    fake_process = "tp-" + "process-secret-not-output"
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", fake_process)
    env_path = tmp_path / "local" / "production_landing.staging.env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(f"XIAOMI_LLM_API_KEY={fake_existing}\n", encoding="utf-8")

    summary = build_production_landing_xiaomi_llm_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert summary["api_key_preserved"] is True
    assert summary["api_key_copied_from_process_env"] is False
    assert f"XIAOMI_LLM_API_KEY={fake_existing}" in env_text
    assert fake_process not in env_text
    assert fake_existing not in summary_text
    assert fake_process not in summary_text
