from __future__ import annotations

import json
from pathlib import Path

from scripts.production_auth_rbac_acceptance import build_production_auth_rbac_acceptance


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_auth_rbac_acceptance_default_skipped(tmp_path: Path) -> None:
    summary = build_production_auth_rbac_acceptance(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["execute"] is False
    assert payload["auth_enabled"] is False
    assert payload["rbac_enabled"] is False
    assert payload["jwt_token_issued"] is False
    assert payload["token_plaintext_output"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_production_auth_rbac_acceptance_execute_success_without_secret_leak(tmp_path: Path) -> None:
    summary = build_production_auth_rbac_acceptance(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )
    statuses = {item["check_id"]: item["status"] for item in payload["checks"]}

    assert payload["status"] == "success"
    assert payload["auth_enabled"] is True
    assert payload["rbac_enabled"] is True
    assert payload["jwt_token_issued"] is True
    assert payload["deployment_error_count"] == 0
    assert statuses["unauthenticated_metrics_endpoint_rejected"] == "success"
    assert statuses["viewer_denied_task_create"] == "success"
    assert statuses["operator_can_read_metrics"] == "success"
    assert statuses["auditor_can_read_audit"] == "success"
    assert statuses["viewer_denied_audit_read"] == "success"
    assert "auth-rbac-acceptance-secret-32-bytes" not in merged
    assert "Bearer " not in merged
    assert "eyJ" not in merged
    assert payload["token_plaintext_output"] is False
    assert payload["secret_plaintext_output"] is False


def test_production_auth_rbac_acceptance_report_files_exist(tmp_path: Path) -> None:
    summary = build_production_auth_rbac_acceptance(output_dir=tmp_path / "out", execute=True)

    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()
    assert summary["check_count"] >= 6
