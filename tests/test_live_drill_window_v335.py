from __future__ import annotations

import json
from pathlib import Path

import scripts.live_drill_window as live_drill


def test_live_drill_generates_json_and_markdown(tmp_path: Path):
    summary = live_drill.build_live_drill_window_summary(output_dir=tmp_path / "out", base_url="http://127.0.0.1:1")
    json_path = Path(summary["json_path"])
    md_path = Path(summary["markdown_path"])

    assert json_path.exists()
    assert md_path.exists()
    assert summary["real_llm_executed"] is False
    assert summary["read_only"] is True

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["generated_at"]
    assert payload["commit"]
    assert payload["mode"] == "fake_offline_default"


def test_live_drill_missing_opt_in_or_oidc_conditions_returns_skipped(tmp_path: Path, monkeypatch):
    for key in live_drill.REQUIRED_REAL_LLM_ENV:
        monkeypatch.delenv(key, raising=False)
    for key in live_drill.OIDC_REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)

    summary = live_drill.build_live_drill_window_summary(output_dir=tmp_path / "out", base_url="http://127.0.0.1:1")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert payload["missing_conditions"]
    assert any("REAL_LLM_SMOKE_ENABLED" in item for item in payload["missing_conditions"])
    assert summary["status"] == "skipped"


def test_live_drill_only_service_unavailable_returns_partial(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "fake-model")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-placeholder-not-output")

    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://idp.example.com/realms/demo")
    monkeypatch.setenv("OIDC_CLIENT_ID", "project-b-demo")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_ENV", "OIDC_CLIENT_SECRET")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "placeholder-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example.com/auth/callback")

    summary = live_drill.build_live_drill_window_summary(output_dir=tmp_path / "out", base_url="http://127.0.0.1:1")
    assert summary["status"] == "partial"


def test_live_drill_script_missing_returns_blocked(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        live_drill,
        "_build_script_readiness",
        lambda: ([{"script": "scripts/acceptance_snapshot.py", "exists": False}], ["script_missing:scripts/acceptance_snapshot.py"]),
    )
    summary = live_drill.build_live_drill_window_summary(output_dir=tmp_path / "out", base_url="http://127.0.0.1:1")
    assert summary["status"] == "blocked"


def test_live_drill_no_secret_plaintext_leak(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-very-secret-token")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_ENV", "OIDC_CLIENT_SECRET")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")

    summary = live_drill.build_live_drill_window_summary(output_dir=tmp_path / "out", base_url="http://127.0.0.1:1")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-very-secret-token" not in merged
    assert "top-secret" not in merged
    assert "OPENAI_API_KEY" in merged
    assert "OIDC_CLIENT_SECRET" in merged
