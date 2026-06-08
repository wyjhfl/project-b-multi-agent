from __future__ import annotations

import json
from pathlib import Path

from app.harness.llm.preflight import LLMPreflightResult
from scripts.production_landing_real_llm_preflight_runner import (
    build_production_landing_real_llm_preflight_runner,
)


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _merged(summary: dict) -> str:
    return Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )


def test_real_llm_preflight_runner_skips_without_process_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("REAL_LLM_API_KEY", raising=False)

    summary = build_production_landing_real_llm_preflight_runner(
        output_dir=tmp_path / "out",
        model="gpt-5.5",
        base_url="http://100.119.206.22:8300/v1",
        api_key_env="REAL_LLM_API_KEY",
    )
    payload = _payload(summary)

    assert summary["status"] == "skipped"
    assert summary["api_key_present"] is False
    assert summary["real_llm_executed"] is False
    assert payload["env_file_written"] is False
    assert payload["local_env_modified"] is False
    assert payload["api_key_env"] == "REAL_LLM_API_KEY"
    assert payload["real_llm_model"] == "gpt-5.5"
    assert payload["preflight"]["base_url_host"] == "100.119.206.22:8300"
    assert payload["preflight"]["base_url"] == "http://100.119.206.22:8300"
    assert payload["real_llm_base_url"] == "http://100.119.206.22:8300"
    assert "missing_process_env:REAL_LLM_API_KEY" in payload["warnings"]
    assert "missing_process_env:REAL_LLM_API_KEY" in payload["acceptance_blockers"]
    assert payload["safe_next_action"] == "run_scripts_real_llm_preflight_ps1_and_enter_key_securely"
    assert payload["secret_plaintext_output"] is False


def test_real_llm_preflight_runner_ready_without_network_and_without_secret_leak(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_key = "k-" + "local-real-secret-not-output-1234567890"
    monkeypatch.setenv("REAL_LLM_API_KEY", fake_key)

    summary = build_production_landing_real_llm_preflight_runner(
        output_dir=tmp_path / "out",
        model="gpt-5.5",
        base_url="http://100.119.206.22:8300/v1",
        api_key_env="REAL_LLM_API_KEY",
    )
    payload = _payload(summary)
    merged = _merged(summary)

    assert summary["status"] == "partial"
    assert payload["preflight"]["preflight_status"] == "ready"
    assert payload["preflight"]["api_key_present"] is True
    assert payload["preflight"]["network_check_executed"] is False
    assert payload["real_llm_executed"] is False
    assert fake_key not in merged
    assert payload["secret_plaintext_output"] is False
    assert "network_check_not_requested" in payload["acceptance_blockers"]
    assert payload["safe_next_action"] == "rerun_with_execute_network_check"


def test_real_llm_preflight_runner_executes_network_check_with_mocked_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.production_landing_real_llm_preflight_runner as runner

    fake_key = "k-" + "local-real-secret-not-output-1234567890"
    monkeypatch.setenv("REAL_LLM_API_KEY", fake_key)

    def fake_preflight(*, perform_network_check: bool) -> LLMPreflightResult:
        return LLMPreflightResult(
            allowed=True,
            status="passed",
            provider="litellm",
            model="gpt-5.5",
            base_url="http://100.119.206.22:8300/v1",
            api_key_env="REAL_LLM_API_KEY",
            api_key_present=True,
            network_check_allowed=True,
            network_check_requested=perform_network_check,
            network_check_executed=True,
            checks=[{"name": "network_check", "ok": True, "detail": "network_check_ok"}],
            warnings=[],
            errors=[],
            latency_ms=18.5,
        )

    monkeypatch.setattr(runner, "run_llm_provider_preflight", fake_preflight)

    summary = build_production_landing_real_llm_preflight_runner(
        output_dir=tmp_path / "out",
        execute_network_check=True,
        model="gpt-5.5",
        base_url="http://100.119.206.22:8300/v1",
        api_key_env="REAL_LLM_API_KEY",
    )
    payload = _payload(summary)
    merged = _merged(summary)

    assert summary["status"] == "success"
    assert summary["real_llm_executed"] is True
    assert payload["preflight"]["network_check_executed"] is True
    assert payload["preflight"]["latency_ms"] == 18.5
    assert fake_key not in merged
    assert payload["secret_plaintext_output"] is False
    assert payload["acceptance_blockers"] == []


def test_real_llm_preflight_runner_blocks_and_redacts_base_url_userinfo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("REAL_LLM_API_KEY", "k-local-real-secret-not-output-1234567890")

    summary = build_production_landing_real_llm_preflight_runner(
        output_dir=tmp_path / "out",
        execute_network_check=True,
        model="gpt-5.5",
        base_url="https://user:pass@example.test:8300/v1?token=bad",
        api_key_env="REAL_LLM_API_KEY",
    )
    payload = _payload(summary)
    merged = _merged(summary)

    assert summary["status"] == "blocked"
    assert payload["secret_plaintext_output"] is False
    assert payload["preflight"]["base_url"] == "https://example.test:8300"
    assert payload["preflight"]["base_url_summary"] == "https://example.test:8300"
    assert payload["preflight"]["base_url_host"] == "example.test:8300"
    assert payload["real_llm_base_url"] == "https://example.test:8300"
    assert "real_llm_base_url_contains_userinfo" in payload["errors"]
    assert "user:pass" not in merged
    assert "token=bad" not in merged
