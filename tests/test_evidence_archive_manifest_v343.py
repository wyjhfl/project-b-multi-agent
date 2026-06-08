from __future__ import annotations

import json
from pathlib import Path

from scripts.evidence_archive_manifest import build_evidence_archive_manifest
from scripts import evidence_archive_manifest


def _write(path: Path, text: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_evidence_archive_manifest_handles_empty_roots(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
    }

    summary = build_evidence_archive_manifest(output_dir=tmp_path / "out", evidence_roots=roots)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["total_files"] == 0
    assert set(payload["missing_expected_types"]) == {"acceptance_snapshot", "demo_artifact"}
    assert Path(summary["markdown_path"]).exists()


def test_evidence_archive_manifest_indexes_latest_by_type(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
    }
    _write(roots["acceptance_snapshot"] / "a.json")
    _write(roots["demo_artifact"] / "b.md", "# demo")

    summary = build_evidence_archive_manifest(output_dir=tmp_path / "out", evidence_roots=roots)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "success"
    assert payload["total_files"] == 2
    assert set(payload["latest_by_type"]) == {"acceptance_snapshot", "demo_artifact"}
    assert payload["retention_policy"]["deletion_enabled"] is False


def test_evidence_archive_manifest_partial_missing_is_warning(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
    }
    _write(roots["acceptance_snapshot"] / "a.json")

    summary = build_evidence_archive_manifest(output_dir=tmp_path / "out", evidence_roots=roots)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "warning"
    assert payload["missing_expected_types"] == ["demo_artifact"]


def test_evidence_archive_manifest_does_not_read_or_leak_secret_content(tmp_path: Path):
    roots = {"acceptance_snapshot": tmp_path / "acceptance"}
    _write(
        roots["acceptance_snapshot"] / "secret.json",
        '{"api_key": "sk-secret-never-output", "database_url": "postgresql://demo:secret@localhost/db"}',
    )

    summary = build_evidence_archive_manifest(output_dir=tmp_path / "out", evidence_roots=roots)
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-secret-never-output" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "secret.json" in merged


def test_evidence_archive_manifest_default_roots_include_controlled_pilot_run_packet():
    assert "controlled_pilot_run_packet" in evidence_archive_manifest.DEFAULT_EVIDENCE_ROOTS
    assert (
        evidence_archive_manifest.DEFAULT_EVIDENCE_ROOTS["controlled_pilot_run_packet"].as_posix()
        .endswith("docs/reports/controlled_pilot_run_packet")
    )
