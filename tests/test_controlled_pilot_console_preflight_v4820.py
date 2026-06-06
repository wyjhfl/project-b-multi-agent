from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_console_preflight import build_controlled_pilot_console_preflight


def _build_tree(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    for name in [
        "codex_python.ps1",
        "controlled_pilot_console_up.ps1",
        "controlled_pilot_console_down.ps1",
        "controlled_pilot_console_verify.ps1",
    ]:
        (root / "scripts" / name).write_text("# test", encoding="utf-8")
    next_cli = root / "frontend" / "node_modules" / "next" / "dist" / "bin"
    next_cli.mkdir(parents=True)
    (next_cli / "next").write_text("#!/usr/bin/env node", encoding="utf-8")
    (root / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    (root / "frontend" / ".next").mkdir(parents=True)
    (root / "frontend" / ".next" / "BUILD_ID").write_text("build-id", encoding="utf-8")


def test_controlled_pilot_console_preflight_ready(tmp_path: Path, monkeypatch) -> None:
    _build_tree(tmp_path)
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight.CONSOLE_RUNTIME_DIR",
        tmp_path / "docs" / "reports" / "controlled_pilot_console",
    )
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight.VERIFY_REPORT_DIR",
        tmp_path / "docs" / "reports" / "controlled_pilot_console_verify",
    )
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.shutil.which", lambda name: f"C:/bin/{name}")
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight._port_is_listening", lambda host, port: False)

    summary = build_controlled_pilot_console_preflight(output_dir=tmp_path / "out")

    assert summary["status"] == "ready"
    assert summary["ready_for_local_verify"] is True
    assert summary["blocking_condition_count"] == 0
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["real_llm_executed"] is False
    assert summary["secret_plaintext_output"] is False
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_controlled_pilot_console_preflight_blocks_missing_build_and_busy_port(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_tree(tmp_path)
    (tmp_path / "frontend" / ".next" / "BUILD_ID").unlink()
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight.CONSOLE_RUNTIME_DIR",
        tmp_path / "docs" / "reports" / "controlled_pilot_console",
    )
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight.VERIFY_REPORT_DIR",
        tmp_path / "docs" / "reports" / "controlled_pilot_console_verify",
    )
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.shutil.which", lambda name: f"C:/bin/{name}")
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight._port_is_listening",
        lambda host, port: port == 3003,
    )

    summary = build_controlled_pilot_console_preflight(output_dir=tmp_path / "out")

    assert summary["status"] == "blocked"
    assert summary["ready_for_local_verify"] is False
    assert "next_build_id_present:missing_or_false" in summary["blocking_conditions"]
    assert "frontend_port:3003:already_listening" in summary["blocking_conditions"]
    assert summary["public_production_direct_launch"] == "No-Go"


def test_controlled_pilot_console_preflight_reads_latest_verify_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_tree(tmp_path)
    verify_dir = tmp_path / "docs" / "reports" / "controlled_pilot_console_verify"
    verify_dir.mkdir(parents=True)
    (verify_dir / "001_controlled_pilot_console_verify.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T10:00:00+00:00",
                "status": "success",
                "controlled_internal_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "missing_condition_count": 0,
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_preflight.CONSOLE_RUNTIME_DIR",
        tmp_path / "docs" / "reports" / "controlled_pilot_console",
    )
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.VERIFY_REPORT_DIR", verify_dir)
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight.shutil.which", lambda name: f"C:/bin/{name}")
    monkeypatch.setattr("scripts.controlled_pilot_console_preflight._port_is_listening", lambda host, port: False)

    summary = build_controlled_pilot_console_preflight(output_dir=tmp_path / "out")

    assert summary["latest_verify"]["latest_report_present"] is True
    assert summary["latest_verify"]["status"] == "success"
    assert summary["latest_verify"]["controlled_internal_pilot"] == "Go"
    assert summary["latest_verify"]["public_production_direct_launch"] == "No-Go"
