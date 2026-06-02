from __future__ import annotations

import json
from pathlib import Path

from scripts.identity_tenant_boundary_inventory import build_identity_tenant_boundary_inventory


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_identity_tenant_boundary_inventory_generates_outputs(tmp_path: Path) -> None:
    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["real_idp_connected"] is False
    assert summary["tenant_enforcement_enabled"] is False
    assert payload["version"] == "3.5.0"
    assert payload["phase"] == "v3.6 Phase 16.1"
    assert payload["output_dir"] == str(tmp_path / "out")
    assert Path(summary["markdown_path"]).exists()


def test_identity_tenant_boundary_inventory_records_existing_auth_rbac_oidc(tmp_path: Path) -> None:
    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["identity_model"]["user_model"]["fields"] == [
        "created_at",
        "disabled",
        "password_hash",
        "roles",
        "user_id",
        "username",
    ]
    assert payload["identity_model"]["token_payload"]["fields"] == ["exp", "roles", "sub"]
    assert "admin" in payload["rbac"]["role_hierarchy"]
    assert "tasks:create" in payload["rbac"]["endpoint_permissions"]
    assert payload["oidc"]["status_api"] == "/auth/oidc/status"
    assert payload["oidc"]["secret_output_policy"] == "client_secret_present_bool_only"


def test_identity_tenant_boundary_inventory_marks_tenant_scope_gaps(tmp_path: Path) -> None:
    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    gap_ids = {item["gap_id"] for item in payload["gaps"]}

    assert "identity:user_model_tenant_scope_missing" in gap_ids
    assert "identity:token_payload_tenant_scope_missing" in gap_ids
    assert "tenant:ownership_model_missing" not in gap_ids
    assert "tenant:runtime_enforcement_missing" in gap_ids
    assert "audit:tenant_scope_missing" in gap_ids
    assert payload["gap_count"] == len(payload["gaps"])


def test_identity_tenant_boundary_inventory_preserves_default_offline_boundaries(tmp_path: Path) -> None:
    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["default_auth_enabled"] is False
    assert payload["default_rbac_enabled"] is False
    assert payload["default_oidc_enabled"] is False
    assert payload["business_data_written"] is False
    assert payload["oidc_token_exchange_executed"] is False
    assert payload["resource_ownership"]["runtime_enforcement_enabled"] is False


def test_identity_tenant_boundary_inventory_does_not_emit_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@localhost/db")

    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "top-secret" not in merged
    assert "jwt-secret-value" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "OIDC_CLIENT_SECRET" in merged
    assert "JWT_SECRET" in merged
    assert "DATABASE_URL" in merged
