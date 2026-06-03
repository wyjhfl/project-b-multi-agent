from __future__ import annotations

import json
from pathlib import Path

from scripts.rbac_permission_matrix import build_rbac_permission_matrix


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_rbac_permission_matrix_generates_outputs(tmp_path: Path) -> None:
    summary = build_rbac_permission_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["real_idp_connected"] is False
    assert summary["auth_logic_changed"] is False
    assert payload["version"] == "3.6.0"
    assert payload["phase"] == "v3.6 Phase 16.3"
    assert payload["output_dir"] == str(tmp_path / "out")
    assert Path(summary["markdown_path"]).exists()


def test_rbac_permission_matrix_covers_current_permissions(tmp_path: Path) -> None:
    summary = build_rbac_permission_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    permissions = {row["permission"] for row in payload["permissions"]}

    assert {
        "tasks:create",
        "tasks:read",
        "approvals:decide",
        "approvals:read",
        "audit:read",
        "audit:export",
        "metrics:read",
        "tools:call",
        "tools:read",
        "eval:run",
        "eval:read",
        "memory:manage",
        "reflection:run",
        "snapshot:manage",
    } <= permissions
    assert payload["permission_count"] == len(payload["permissions"])


def test_rbac_permission_matrix_preserves_expected_denials(tmp_path: Path) -> None:
    summary = build_rbac_permission_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    by_permission = {row["permission"]: row for row in payload["permissions"]}

    assert by_permission["tasks:create"]["role_matrix"]["viewer"]["allowed"] is False
    assert by_permission["tasks:create"]["role_matrix"]["operator"]["allowed"] is True
    assert by_permission["audit:read"]["role_matrix"]["operator"]["allowed"] is False
    assert by_permission["audit:read"]["role_matrix"]["auditor"]["allowed"] is True
    assert by_permission["tools:call"]["role_matrix"]["viewer"]["allowed"] is False
    assert by_permission["snapshot:manage"]["role_matrix"]["operator"]["allowed"] is False


def test_rbac_permission_matrix_includes_rejection_evidence_and_review_process(tmp_path: Path) -> None:
    summary = build_rbac_permission_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    for row in payload["permissions"]:
        assert row["rejection_evidence"]["missing_or_invalid_token"] == 401
        assert row["rejection_evidence"]["authenticated_but_not_authorized"] == 403
        assert "least_privilege_note" in row
    assert "permission_request" in payload["review_process"]
    assert "periodic_review" in payload["review_process"]
    assert payload["denied_pair_count"] == len(payload["denied_pairs"])


def test_rbac_permission_matrix_keeps_default_offline_boundary(tmp_path: Path) -> None:
    summary = build_rbac_permission_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["default_auth_enabled"] is False
    assert payload["default_rbac_enabled"] is False
    assert payload["tenant_enforcement_enabled"] is False
    assert payload["require_permission_bypassed"] is False
    assert "不默认启用 AUTH_ENABLED 或 RBAC_ENABLED" in payload["boundary_declarations"]
