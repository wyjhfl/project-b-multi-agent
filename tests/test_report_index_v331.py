from __future__ import annotations

import json
from pathlib import Path

from scripts.report_index import build_report_index


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_report_index_handles_empty_dirs(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
        "failure_diagnostics": tmp_path / "failure",
    }
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)

    summary = build_report_index(output_dir=tmp_path / "out", report_roots=roots, retention_keep_latest=2, retention_days=1)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()
    assert len(payload["report_index"]) == 3
    for item in payload["report_index"]:
        assert item["file_count"] == 0
        assert item["stale_candidates"] == []


def test_report_index_recognizes_three_report_types(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
        "failure_diagnostics": tmp_path / "failure",
    }
    _write(roots["acceptance_snapshot"] / "a.json", {"status": "ok"})
    _write(roots["demo_artifact"] / "b.json", {"status": "ok"})
    _write(roots["failure_diagnostics"] / "c.json", {"status": "ok"})

    summary = build_report_index(output_dir=tmp_path / "out", report_roots=roots, retention_keep_latest=5, retention_days=30)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    kinds = {item["report_type"] for item in payload["report_index"]}
    assert kinds == {"acceptance_snapshot", "demo_artifact", "failure_diagnostics"}


def test_report_index_lists_stale_candidates_without_deleting(tmp_path: Path):
    root = tmp_path / "acceptance"
    first = root / "1.json"
    second = root / "2.json"
    third = root / "3.json"
    _write(first, {"x": 1})
    _write(second, {"x": 2})
    _write(third, {"x": 3})

    roots = {
        "acceptance_snapshot": root,
        "demo_artifact": tmp_path / "demo",
        "failure_diagnostics": tmp_path / "failure",
    }
    roots["demo_artifact"].mkdir(parents=True, exist_ok=True)
    roots["failure_diagnostics"].mkdir(parents=True, exist_ok=True)

    summary = build_report_index(output_dir=tmp_path / "out", report_roots=roots, retention_keep_latest=1, retention_days=9999)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    item = next(x for x in payload["report_index"] if x["report_type"] == "acceptance_snapshot")
    assert item["file_count"] == 3
    assert len(item["stale_candidates"]) >= 2
    assert first.exists() and second.exists() and third.exists()
    assert item["retention_policy"]["deletion_enabled"] is False


def test_report_index_does_not_leak_sensitive_values(tmp_path: Path):
    roots = {
        "acceptance_snapshot": tmp_path / "acceptance",
        "demo_artifact": tmp_path / "demo",
        "failure_diagnostics": tmp_path / "failure",
    }
    _write(
        roots["acceptance_snapshot"] / "sensitive.json",
        {
            "prompt": "raw prompt should never be copied",
            "api_key": "sk-secret-never-output",
            "database_url": "postgresql://demo:secret@localhost:5432/demo",
            "client_secret": "super-secret",
        },
    )
    roots["demo_artifact"].mkdir(parents=True, exist_ok=True)
    roots["failure_diagnostics"].mkdir(parents=True, exist_ok=True)

    summary = build_report_index(output_dir=tmp_path / "out", report_roots=roots)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "raw prompt should never be copied" not in merged
    assert "sk-secret-never-output" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "super-secret" not in merged
