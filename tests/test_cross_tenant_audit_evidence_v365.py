from __future__ import annotations

import json
from pathlib import Path

from scripts.cross_tenant_audit_evidence import build_cross_tenant_audit_evidence


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_cross_tenant_audit_evidence_generates_default_template(tmp_path: Path) -> None:
    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["real_idp_connected"] is False
    assert summary["tenant_enforcement_enabled"] is False
    assert summary["audit_store_schema_changed"] is False
    assert payload["version"] == "3.6.0"
    assert payload["phase"] == "v3.6 Phase 16.5"
    assert payload["missing_conditions"]
    assert Path(summary["markdown_path"]).exists()


def test_cross_tenant_audit_evidence_includes_required_scope_fields_and_templates(tmp_path: Path) -> None:
    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert {
        "organization_id",
        "tenant_id",
        "project_id",
        "resource_id",
        "actor_principal_id",
        "decision",
        "denial_reason",
    } <= set(payload["required_audit_scope_fields"])
    template_ids = {item["template_id"] for item in payload["evidence_templates"]}
    assert {
        "allow_evidence",
        "deny_evidence",
        "audit_record_evidence",
        "export_redaction_evidence",
        "reviewer_owner_evidence",
    } <= template_ids


def test_cross_tenant_audit_evidence_preserves_runtime_boundaries(tmp_path: Path) -> None:
    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["audit_store_schema_changed"] is False
    assert payload["tenant_enforcement_enabled"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["prompt_plaintext_output"] is False
    assert payload["jwt_payload_changed"] is False


def test_cross_tenant_audit_evidence_loads_rbac_metadata_only(tmp_path: Path) -> None:
    rbac_path = tmp_path / "rbac.json"
    rbac_path.write_text(
        json.dumps(
            {
                "version": "3.6.0",
                "phase": "v3.6 Phase 16.3",
                "status": "success",
                "read_only": True,
                "real_llm_executed": False,
                "real_idp_connected": False,
                "tenant_enforcement_enabled": False,
                "permission_count": 14,
                "denied_pair_count": 18,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out", rbac_matrix=rbac_path)
    payload = _read_payload(summary)
    source = next(item for item in payload["sources"] if item["name"] == "rbac_matrix")

    assert source["loaded"] is True
    assert source["metadata"]["phase"] == "v3.6 Phase 16.3"
    assert source["metadata"]["permission_count"] == 14
    assert "permissions" not in source["metadata"]


def test_cross_tenant_audit_evidence_blocks_sensitive_input_without_leaking(tmp_path: Path) -> None:
    sample_path = tmp_path / "audit_sample.json"
    sample_path.write_text(
        json.dumps(
            {
                "status": "success",
                "read_only": True,
                "detail": {
                    "token": "token-plain",
                    "prompt": "原始 prompt 不能导出",
                    "database_url": "postgresql+psycopg://agent:db-password@db:5432/project_b",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out", audit_export_sample=sample_path)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is False
    assert payload["prompt_plaintext_output"] is False
    assert "token-plain" not in merged
    assert "原始 prompt 不能导出" not in merged
    assert "db-password" not in merged
    assert any("sensitive_plaintext_detected" in item for item in payload["missing_conditions"])


def test_cross_tenant_audit_evidence_records_tenant_doc_metadata_without_content(tmp_path: Path) -> None:
    doc_path = tmp_path / "tenant_model.md"
    doc_path.write_text("这里即使包含说明，也不应进入 source metadata。", encoding="utf-8")

    summary = build_cross_tenant_audit_evidence(output_dir=tmp_path / "out", tenant_model_doc=doc_path)
    payload = _read_payload(summary)
    source = next(item for item in payload["sources"] if item["name"] == "tenant_model_doc")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert source["exists"] is True
    assert source["metadata"]["content_read_for_output"] is False
    assert "这里即使包含说明" not in merged
