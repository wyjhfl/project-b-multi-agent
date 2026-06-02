from __future__ import annotations

import json
from pathlib import Path

from scripts.pilot_handoff_checklist import build_pilot_handoff_checklist


def test_pilot_handoff_checklist_generates_json_and_markdown(tmp_path: Path):
    summary = build_pilot_handoff_checklist(output_dir=tmp_path / "handoff")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert payload["version"] == "3.5.0"
    assert Path(summary["markdown_path"]).exists()


def test_pilot_handoff_checklist_roles_and_go_no_go(tmp_path: Path):
    summary = build_pilot_handoff_checklist(output_dir=tmp_path / "handoff")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    roles = {item["role"] for item in payload["roles"]}

    assert {"admin", "operator", "viewer", "auditor"} <= roles
    assert payload["go_no_go"]["intranet_pilot"] == "Go"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_pilot_handoff_checklist_links_required_evidence(tmp_path: Path):
    summary = build_pilot_handoff_checklist(output_dir=tmp_path / "handoff")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    merged_paths = "\n".join(path for item in payload["handoff_items"] for path in item["evidence_paths"])

    assert "docs/incident_rehearsal_pack_v34.md" in merged_paths
    assert "docs/evidence_archive_manifest_v34.md" in merged_paths
    assert "docs/optional_integration_readiness_matrix_v34.md" in merged_paths
    assert "docs/backup_restore_checklist_v31.md" in merged_paths


def test_pilot_handoff_checklist_no_secret_plaintext_leak(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")

    summary = build_pilot_handoff_checklist(output_dir=tmp_path / "handoff")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-sensitive-value" not in merged
    assert "top-secret" not in merged
