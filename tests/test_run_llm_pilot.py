from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.harness.eval.cases import EvalCaseLoader
from scripts import run_llm_pilot


def _clear_pilot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PILOT_PROVIDER", "PILOT_MODEL", "PILOT_BASE_URL", "PILOT_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def _set_default_real_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", False)
    monkeypatch.setattr(settings, "real_llm_provider", "litellm")
    monkeypatch.setattr(settings, "real_llm_model", "")
    monkeypatch.setattr(settings, "real_llm_base_url", "")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "OPENAI_API_KEY")


def _load_report_files(output_dir: Path) -> tuple[Path, Path]:
    json_files = list(output_dir.glob("*.json"))
    md_files = list(output_dir.glob("*.md"))
    assert len(json_files) == 1
    assert len(md_files) == 1
    return json_files[0], md_files[0]


def test_dry_run_end_to_end_generates_marked_report(tmp_path, monkeypatch, capsys):
    _clear_pilot_env(monkeypatch)
    exit_code = run_llm_pilot.main(["--dry-run", "--output-dir", str(tmp_path), "--limit", "6"])
    assert exit_code == 0

    json_path, md_path = _load_report_files(tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_mode"] == "dry_run"
    assert payload["provider"] == "fake"
    assert payload["model"] == "fake-offline"
    assert "base_url_summary" in payload
    assert payload["eval_summary"]["run_mode"] == "dry_run"
    assert payload["eval_summary"]["cases_total"] == 6
    assert payload["real_call_attempted"] is False

    md_text = md_path.read_text(encoding="utf-8")
    assert "DRY RUN" in md_text
    assert "run_mode: dry_run" in md_text
    assert "NL2SQL Eval 汇总" in md_text

    out = capsys.readouterr().out
    assert "DRY RUN" in out


def test_dry_run_report_contains_summary_metrics_and_no_prompt(tmp_path, monkeypatch):
    _clear_pilot_env(monkeypatch)
    exit_code = run_llm_pilot.main(["--dry-run", "--output-dir", str(tmp_path)])
    assert exit_code == 0

    json_path, md_path = _load_report_files(tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    summary = payload["eval_summary"]
    for field in (
        "success_rate",
        "fallback_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "total_tokens_total",
        "cost_total_usd",
        "bad_cases",
    ):
        assert field in summary
    assert summary["cases_total"] == len(payload["cases"]) - 1
    # token 汇总字段是数值，不得被脱敏规则误伤为占位符
    assert isinstance(summary["prompt_tokens_total"], int)
    assert isinstance(summary["completion_tokens_total"], int)
    assert isinstance(summary["total_tokens_total"], int)

    # 脱敏：报告不得含 eval 用例的用户输入原文与危险 SQL 原文
    report_text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for case in EvalCaseLoader().load():
        assert case.input not in report_text
        if case.raw_sql:
            assert case.raw_sql not in report_text


def test_real_mode_refuses_without_any_config(tmp_path, monkeypatch, capsys):
    _clear_pilot_env(monkeypatch)
    _set_default_real_llm_settings(monkeypatch)

    exit_code = run_llm_pilot.main(["--output-dir", str(tmp_path)])
    assert exit_code == 2
    assert list(tmp_path.iterdir()) == []

    out = capsys.readouterr().out
    assert "拒绝生成报告" in out
    assert "REAL_LLM_ACCEPTANCE_ENABLED" in out
    assert "--dry-run" in out


def test_real_mode_refuses_when_api_key_missing(tmp_path, monkeypatch, capsys):
    _clear_pilot_env(monkeypatch)
    _set_default_real_llm_settings(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(settings, "real_llm_api_key_env", "PILOT_TEST_KEY_ENV")
    monkeypatch.delenv("PILOT_TEST_KEY_ENV", raising=False)

    exit_code = run_llm_pilot.main(["--output-dir", str(tmp_path)])
    assert exit_code == 2
    assert list(tmp_path.iterdir()) == []

    out = capsys.readouterr().out
    assert "PILOT_TEST_KEY_ENV" in out


def test_collect_refusal_reasons_passes_when_fully_configured(monkeypatch):
    _clear_pilot_env(monkeypatch)
    _set_default_real_llm_settings(monkeypatch)
    monkeypatch.setattr(settings, "real_llm_acceptance_enabled", True)
    monkeypatch.setattr(settings, "real_llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "real_llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "real_llm_base_url", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    cfg = run_llm_pilot.resolve_pilot_config(dry_run=False)
    assert cfg.provider == "openai_compatible"
    assert cfg.api_key_present is True
    assert run_llm_pilot.collect_refusal_reasons(cfg) == []


def test_pilot_env_overrides_take_precedence(monkeypatch):
    _clear_pilot_env(monkeypatch)
    _set_default_real_llm_settings(monkeypatch)
    monkeypatch.setenv("PILOT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PILOT_MODEL", "pilot-model")
    monkeypatch.setenv("PILOT_BASE_URL", "https://pilot.example.com/v1")
    monkeypatch.setenv("PILOT_API_KEY", "sk-pilot-not-real")

    cfg = run_llm_pilot.resolve_pilot_config(dry_run=False)
    assert cfg.provider == "openai_compatible"
    assert cfg.model == "pilot-model"
    assert cfg.base_url == "https://pilot.example.com/v1"
    assert cfg.api_key_present is True


def test_dry_run_report_never_contains_api_key(tmp_path, monkeypatch):
    _clear_pilot_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-should-not-leak")

    exit_code = run_llm_pilot.main(["--dry-run", "--output-dir", str(tmp_path), "--limit", "3"])
    assert exit_code == 0
    json_path, md_path = _load_report_files(tmp_path)
    report_text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert "sk-secret-should-not-leak" not in report_text
