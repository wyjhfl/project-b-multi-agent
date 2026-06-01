from __future__ import annotations

import json
from pathlib import Path

from scripts.pilot_evidence_comparison import build_pilot_evidence_comparison


def _write_manifest(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "success",
        "evidence_items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_pilot_evidence_comparison_manifest_to_manifest_success(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_manifest(
        baseline,
        [
            {"path": "docs/reports/a.json", "size_bytes": 10, "modified_at": "2026-01-01T00:00:00+00:00", "extension": ".json"},
            {"path": "docs/reports/b.json", "size_bytes": 20, "modified_at": "2026-01-01T00:00:00+00:00", "extension": ".json"},
        ],
    )
    _write_manifest(
        current,
        [
            {"path": "docs/reports/a.json", "size_bytes": 10, "modified_at": "2026-01-01T00:00:00+00:00", "extension": ".json"},
            {"path": "docs/reports/c.json", "size_bytes": 30, "modified_at": "2026-01-02T00:00:00+00:00", "extension": ".json"},
        ],
    )

    summary = build_pilot_evidence_comparison(
        output_dir=tmp_path / "out",
        baseline=baseline,
        current=current,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["version"] == "3.4.0"
    assert payload["comparison"]["added_paths"] == ["docs/reports/c.json"]
    assert payload["comparison"]["removed_paths"] == ["docs/reports/b.json"]
    assert payload["comparison"]["changed_count"] == 0
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert Path(summary["markdown_path"]).exists()


def test_pilot_evidence_comparison_manifest_changed_file_partial(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_manifest(
        baseline,
        [{"path": "docs/reports/a.json", "size_bytes": 10, "modified_at": "2026-01-01T00:00:00+00:00", "extension": ".json"}],
    )
    _write_manifest(
        current,
        [{"path": "docs/reports/a.json", "size_bytes": 99, "modified_at": "2026-01-03T00:00:00+00:00", "extension": ".json"}],
    )

    summary = build_pilot_evidence_comparison(output_dir=tmp_path / "out", baseline=baseline, current=current)
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["comparison"]["changed_count"] == 1
    assert payload["comparison"]["changed_items"][0]["path"] == "docs/reports/a.json"


def test_pilot_evidence_comparison_missing_or_empty_inputs_skipped(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline_empty"
    current = tmp_path / "current_missing"
    baseline.mkdir(parents=True, exist_ok=True)

    summary = build_pilot_evidence_comparison(output_dir=tmp_path / "out", baseline=baseline, current=current)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["status"] == "skipped"
    assert any("directory_empty" in item for item in payload["warnings"])
    assert any("path_not_found" in item for item in payload["warnings"])


def test_pilot_evidence_comparison_does_not_leak_manifest_secret_content(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_manifest(
        baseline,
        [{"path": "docs/reports/secret.json", "size_bytes": 10, "modified_at": "2026-01-01T00:00:00+00:00", "extension": ".json"}],
    )
    current.write_text(
        '{"status":"success","evidence_items":[{"path":"docs/reports/secret.json","size_bytes":11,"modified_at":"2026-01-02T00:00:00+00:00","extension":".json","api_key":"sk-should-not-leak","database_url":"postgresql://demo:secret@localhost/db"}]}',
        encoding="utf-8",
    )

    summary = build_pilot_evidence_comparison(output_dir=tmp_path / "out", baseline=baseline, current=current)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-should-not-leak" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "docs/reports/secret.json" in merged
