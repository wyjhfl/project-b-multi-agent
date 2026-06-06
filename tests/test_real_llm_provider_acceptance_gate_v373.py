from __future__ import annotations

import json
from pathlib import Path

from scripts.real_llm_provider_acceptance_gate import build_real_llm_provider_acceptance_gate


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_real_llm_env(monkeypatch) -> None:
    for key in [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_PROVIDER",
        "REAL_LLM_MODEL",
        "REAL_LLM_BASE_URL",
        "REAL_LLM_API_KEY_ENV",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_real_llm_provider_gate_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_real_llm_env(monkeypatch)
    summary = build_real_llm_provider_acceptance_gate(output_dir=tmp_path / "out", pilot_report_dir=tmp_path / "missing")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["provider_network_check_executed"] is False
    assert payload["version"] == "3.7.0"
    assert payload["phase"] == "v3.7 Phase 17.3"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_real_llm_provider_gate_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_real_llm_env(monkeypatch)
    summary = build_real_llm_provider_acceptance_gate(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "preflight_config",
        "network_check_gate",
        "smoke_opt_in",
        "budget_cache_fallback",
        "pii_prompt_guardrails",
        "report_redaction",
        "judge_acceptance",
        "evidence_index",
    } <= check_ids


def test_real_llm_provider_gate_partial_when_opt_in_config_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_PROVIDER", "litellm")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder-not-secret")

    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "sample.json").write_text("{}", encoding="utf-8")
    summary = build_real_llm_provider_acceptance_gate(output_dir=tmp_path / "out", pilot_report_dir=report_dir)
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["real_llm_executed"] is False
    assert payload["provider_network_check_executed"] is False
    assert payload["pilot_report_content_read"] is False
    assert payload["pilot_report_index"]["file_count"] == 1


def test_real_llm_provider_gate_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("REAL_LLM_BASE_URL", "https://user:password@example.com/v1")

    summary = build_real_llm_provider_acceptance_gate(output_dir=tmp_path / "out", pilot_report_dir=tmp_path / "missing")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "password@example" not in merged
    assert "REAL_LLM_API_KEY_ENV" in merged
    assert "OPENAI_API_KEY" in merged


def test_real_llm_provider_gate_indexes_report_metadata_only(tmp_path: Path, monkeypatch) -> None:
    _clear_real_llm_env(monkeypatch)
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "report.json").write_text('{"prompt":"raw prompt should not be read"}', encoding="utf-8")
    (report_dir / "report.md").write_text("raw markdown prompt should not be read", encoding="utf-8")

    summary = build_real_llm_provider_acceptance_gate(output_dir=tmp_path / "out", pilot_report_dir=report_dir)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["pilot_report_index"]["content_read"] is False
    assert payload["pilot_report_index"]["file_count"] == 2
    assert "raw prompt should not be read" not in merged
    assert "raw markdown prompt should not be read" not in merged
