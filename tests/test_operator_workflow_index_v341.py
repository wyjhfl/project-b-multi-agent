from __future__ import annotations

import json
from pathlib import Path

from scripts.operator_workflow_index import build_operator_workflow_index


def test_operator_workflow_index_generates_json_and_markdown(tmp_path: Path):
    summary = build_operator_workflow_index(output_dir=tmp_path / "operator")

    assert summary["status"] == "ok"
    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["entry_count"] == 8
    assert summary["missing_entries"] == []
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_operator_workflow_index_entries_cover_required_operator_paths(tmp_path: Path):
    summary = build_operator_workflow_index(output_dir=tmp_path / "operator")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    entry_ids = {entry["entry_id"] for entry in payload["entries"]}

    assert {
        "operations_console",
        "acceptance_snapshot",
        "demo_artifact_bundle",
        "failure_diagnostics",
        "report_index",
        "config_drift",
        "governance_summary",
        "live_drill_window",
    } <= entry_ids

    for entry in payload["entries"]:
        assert entry["when_to_use"]
        assert "failure_or_skipped_interpretation" in entry
        assert entry["read_only"] is True
        assert entry["real_llm_executed"] is False


def test_operator_workflow_index_no_secret_plaintext_leak(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-very-secret-token")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")

    summary = build_operator_workflow_index(output_dir=tmp_path / "operator")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-very-secret-token" not in merged
    assert "top-secret" not in merged
    assert "OPENAI_API_KEY" not in merged
    assert "OIDC_CLIENT_SECRET" not in merged
