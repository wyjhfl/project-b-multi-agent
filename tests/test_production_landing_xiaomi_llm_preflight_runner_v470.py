from __future__ import annotations

import json
from pathlib import Path

from app.harness.llm.preflight import LLMPreflightResult
from scripts.production_landing_xiaomi_llm_preflight_runner import (
    build_production_landing_xiaomi_llm_preflight_runner,
)


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _merged(summary: dict) -> str:
    return Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )


def test_xiaomi_llm_preflight_runner_skips_without_process_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XIAOMI_LLM_API_KEY", raising=False)
    local_env = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_xiaomi_llm_preflight_runner(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "skipped"
    assert summary["api_key_present"] is False
    assert summary["real_llm_executed"] is False
    assert payload["env_file_written"] is False
    assert payload["local_env_modified"] is False
    assert not local_env.exists()
    assert payload["secret_plaintext_output"] is False
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in payload["warnings"]
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in payload["acceptance_blockers"]
    assert "network_check_not_requested" in payload["acceptance_blockers"]
    assert payload["safe_next_action"] == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    assert payload["preflight"]["base_url_host"] == "token-plan-cn.xiaomimimo.com"
    assert payload["preflight"]["provider_endpoint_kind"] == "openai_compatible_chat_completions"


def test_xiaomi_llm_preflight_runner_ready_without_network_and_without_secret_leak(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_key = "tp-" + "local-real-secret-not-output"
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", fake_key)

    summary = build_production_landing_xiaomi_llm_preflight_runner(output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = _merged(summary)

    assert summary["status"] == "partial"
    assert payload["preflight"]["preflight_status"] == "ready"
    assert payload["preflight"]["api_key_present"] is True
    assert payload["preflight"]["network_check_executed"] is False
    assert payload["real_llm_executed"] is False
    assert payload["env_file_written"] is False
    assert fake_key not in merged
    assert payload["secret_plaintext_output"] is False
    assert "network_check_not_requested" in payload["acceptance_blockers"]
    assert payload["safe_next_action"] == "rerun_with_execute_network_check"
    assert payload["preflight"]["timeout_seconds"] == 20.0


def test_xiaomi_llm_preflight_runner_executes_network_check_with_mocked_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.production_landing_real_llm_preflight_runner as runner

    fake_key = "tp-" + "local-real-secret-not-output"
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", fake_key)

    def fake_preflight(*, perform_network_check: bool) -> LLMPreflightResult:
        return LLMPreflightResult(
            allowed=True,
            status="passed",
            provider="litellm",
            model="mimo-v2.5-pro",
            base_url="https://token-plan-cn.xiaomimimo.com/v1",
            api_key_env="XIAOMI_LLM_API_KEY",
            api_key_present=True,
            network_check_allowed=True,
            network_check_requested=perform_network_check,
            network_check_executed=True,
            checks=[{"name": "network_check", "ok": True, "detail": "network_check_ok"}],
            warnings=[],
            errors=[],
            latency_ms=12.5,
        )

    monkeypatch.setattr(runner, "run_llm_provider_preflight", fake_preflight)

    summary = build_production_landing_xiaomi_llm_preflight_runner(
        output_dir=tmp_path / "out",
        execute_network_check=True,
    )
    payload = _payload(summary)
    merged = _merged(summary)

    assert summary["status"] == "success"
    assert summary["real_llm_executed"] is True
    assert payload["preflight"]["network_check_executed"] is True
    assert payload["preflight"]["latency_ms"] == 12.5
    assert payload["env_file_written"] is False
    assert fake_key not in merged
    assert payload["secret_plaintext_output"] is False
    assert payload["acceptance_blockers"] == []
    assert payload["safe_next_action"] == "refresh_landing_status_and_continue_manual_signoff"
