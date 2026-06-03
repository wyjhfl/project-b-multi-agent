from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from scripts.oidc_lifecycle_drill import build_oidc_lifecycle_drill


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_oidc_env(monkeypatch) -> None:
    for key in [
        "OIDC_ENABLED",
        "OIDC_ISSUER_URL",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET_ENV",
        "OIDC_CLIENT_SECRET",
        "OIDC_REDIRECT_URI",
    ]:
        monkeypatch.delenv(key, raising=False)


def _set_base_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_enabled", False)
    monkeypatch.setattr(settings, "oidc_issuer_url", "")
    monkeypatch.setattr(settings, "oidc_client_id", "")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "")
    monkeypatch.setattr(settings, "oidc_scopes", "openid,email,profile")
    monkeypatch.setattr(settings, "oidc_role_claim", "roles")
    monkeypatch.setattr(settings, "oidc_default_role", "viewer")
    monkeypatch.setattr(settings, "oidc_allowed_roles", "admin,operator,viewer,auditor")
    monkeypatch.setattr(settings, "oidc_require_https", True)


def test_oidc_lifecycle_drill_defaults_to_skipped_without_opt_in(tmp_path: Path, monkeypatch) -> None:
    _clear_oidc_env(monkeypatch)
    _set_base_settings(monkeypatch)

    summary = build_oidc_lifecycle_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["real_idp_connected"] is False
    assert summary["oidc_token_exchange_executed"] is False
    assert payload["version"] == "3.6.0"
    assert payload["phase"] == "v3.6 Phase 16.4"
    assert payload["scenario_count"] == len(payload["scenarios"])
    assert Path(summary["markdown_path"]).exists()


def test_oidc_lifecycle_drill_covers_required_scenarios(tmp_path: Path, monkeypatch) -> None:
    _clear_oidc_env(monkeypatch)
    _set_base_settings(monkeypatch)
    summary = build_oidc_lifecycle_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    scenario_ids = {item["scenario_id"] for item in payload["scenarios"]}

    assert {
        "configuration_preflight",
        "token_lifecycle",
        "logout_session",
        "jwks_rotation",
        "client_secret_rotation",
        "failure_paths",
    } <= scenario_ids


def test_oidc_lifecycle_drill_only_outputs_secret_presence(tmp_path: Path, monkeypatch) -> None:
    _set_base_settings(monkeypatch)
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://idp.example.com/realms/demo")
    monkeypatch.setenv("OIDC_CLIENT_ID", "project-b")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_ENV", "OIDC_CLIENT_SECRET")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "very-secret-value")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://console.example.com/auth/callback")
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://idp.example.com/realms/demo")
    monkeypatch.setattr(settings, "oidc_client_id", "project-b")
    monkeypatch.setattr(settings, "oidc_client_secret_env", "OIDC_CLIENT_SECRET")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://console.example.com/auth/callback")

    summary = build_oidc_lifecycle_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "partial"
    assert payload["env_presence"]["OIDC_CLIENT_SECRET_ENV_TARGET"]["present"] is True
    assert payload["oidc_status"]["client_secret_present"] is True
    assert payload["oidc_token_exchange_executed"] is False
    assert "very-secret-value" not in merged
    assert "OIDC_CLIENT_SECRET" in merged


def test_oidc_lifecycle_drill_records_missing_conditions_for_each_scenario(tmp_path: Path, monkeypatch) -> None:
    _clear_oidc_env(monkeypatch)
    _set_base_settings(monkeypatch)
    summary = build_oidc_lifecycle_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert "env:OIDC_ENABLED" in payload["missing_conditions"]
    assert "opt_in:OIDC_ENABLED_not_true" in payload["missing_conditions"]
    for scenario in payload["scenarios"]:
        assert scenario["status"] == "skipped"
        assert scenario["missing_conditions"]
        assert scenario["real_idp_connected"] is False
        assert scenario["token_exchange_executed"] is False


def test_oidc_lifecycle_drill_keeps_default_offline_boundary(tmp_path: Path, monkeypatch) -> None:
    _clear_oidc_env(monkeypatch)
    _set_base_settings(monkeypatch)
    summary = build_oidc_lifecycle_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["default_auth_enabled"] is False
    assert payload["default_rbac_enabled"] is False
    assert payload["default_oidc_enabled"] is False
    assert payload["client_secret_plaintext_output"] is False
    assert payload["token_plaintext_output"] is False
    assert "不宣称生产级 SSO/OIDC 已完成" in payload["boundary_declarations"]
