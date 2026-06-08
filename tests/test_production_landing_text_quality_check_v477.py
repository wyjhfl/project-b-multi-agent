from __future__ import annotations

import json
from pathlib import Path

import scripts.production_landing_text_quality_check as text_quality
from scripts.production_landing_text_quality_check import build_production_landing_text_quality_check


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_landing_text_quality_check_accepts_clean_files(tmp_path: Path) -> None:
    target = tmp_path / "runbook.md"
    target.write_text("生产落地 Runbook\npublic_production_direct_launch=No-Go\n", encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert summary["blocked_file_count"] == 0
    assert payload["files"][0]["status"] == "success"
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_text_quality_check_blocks_common_mojibake_phrase(tmp_path: Path) -> None:
    target = tmp_path / "bad.md"
    target.write_text("閻㈢喍楠囬拃钘夋勾 Runbook\n", encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert payload["blocked_file_count"] == 1
    assert "text:mojibake_marker_detected" in payload["files"][0]["missing_conditions"]


def test_production_landing_text_quality_check_blocks_mojibake(tmp_path: Path) -> None:
    target = tmp_path / "bad.md"
    target.write_text("鐢熵骇 Runbook\n", encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert payload["blocked_file_count"] == 1
    assert payload["files"][0]["mojibake_markers"]
    assert "text:mojibake_marker_detected" in payload["files"][0]["missing_conditions"]


def test_production_landing_text_quality_check_blocks_secret_like_text_without_value_output(tmp_path: Path) -> None:
    target = tmp_path / "bad.md"
    target.write_text("token=sk-should-not-leak\n", encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert payload["files"][0]["secret_like_detected"] is True
    assert "text:secret_like_detected" in payload["files"][0]["missing_conditions"]
    assert "sk-should-not-leak" not in merged


def test_production_landing_text_quality_check_skips_missing_optional_target(
    tmp_path: Path, monkeypatch
) -> None:
    required = tmp_path / "runbook.md"
    optional = tmp_path / "manual_signoff_record.json"
    required.write_text("生产落地 Runbook\n", encoding="utf-8")
    monkeypatch.setattr(text_quality, "DEFAULT_TARGETS", [required, optional])
    monkeypatch.setattr(text_quality, "OPTIONAL_TARGETS", {optional})

    summary = build_production_landing_text_quality_check(output_dir=tmp_path / "out")
    payload = _payload(summary)
    optional_row = next(item for item in payload["files"] if item["path"] == str(optional))

    assert summary["status"] == "success"
    assert optional_row["status"] == "skipped"
    assert optional_row["required"] is False


def test_production_landing_text_quality_check_skips_missing_ignored_report_targets(
    tmp_path: Path, monkeypatch
) -> None:
    required = tmp_path / "runbook.md"
    report_dir = tmp_path / "docs" / "reports" / "manual_signoff_package"
    template = report_dir / "manual_signoff_record.template.json"
    draft = report_dir / "manual_signoff_record.draft.json"
    final = report_dir / "manual_signoff_record.json"
    required.write_text("Production landing Runbook\n", encoding="utf-8")
    monkeypatch.setattr(text_quality, "DEFAULT_TARGETS", [required, template, draft, final])
    monkeypatch.setattr(text_quality, "OPTIONAL_TARGETS", {template, draft, final})

    summary = build_production_landing_text_quality_check(output_dir=tmp_path / "out")
    payload = _payload(summary)
    optional_rows = [item for item in payload["files"] if item["path"] != str(required)]

    assert summary["status"] == "success"
    assert len(optional_rows) == 3
    assert {item["status"] for item in optional_rows} == {"skipped"}
    assert {item["required"] for item in optional_rows} == {False}


def test_production_landing_text_quality_default_targets_include_business_system_files() -> None:
    targets = {path.as_posix() for path in text_quality.DEFAULT_TARGETS}

    assert (text_quality.ROOT_DIR / "pyproject.toml").as_posix() in targets
    assert (text_quality.ROOT_DIR / "docs" / "business_system_read_smoke_v45.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "docs" / "evidence_archive_manifest_v34.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "docs" / "controlled_pilot_run_packet_v49.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "docs" / "demo_business_read_only_interface_v49.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "business_system_read_smoke.py").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "business_system_read_smoke.ps1").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "controlled_pilot_run_packet.py").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "business_system_production_readiness_brief.py").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "business_system_input_packet.py").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "production_landing_blocker_resolution.py").as_posix() in targets


def test_business_system_read_smoke_doc_documents_env_path_and_localhost_tunnel_boundary() -> None:
    text = (text_quality.ROOT_DIR / "docs" / "business_system_read_smoke_v45.md").read_text(encoding="utf-8")

    assert "business_system_read_smoke.ps1 -EnvPath local\\production_landing.staging.env" in text
    assert "BUSINESS_SYSTEM_BASE_URL" in text
    assert "BUSINESS_SYSTEM_TOKEN" in text
    assert "真实 URL/token 仍必须来自当前进程环境、外部 secret manager 或交互式输入" in text
    assert "localhost" in text
    assert "不会被自动判为 local mock" in text
    assert "BUSINESS_SYSTEM_NAME=local_business_read_mock" in text


def test_production_landing_text_quality_check_blocks_pyproject_mojibake_marker(tmp_path: Path) -> None:
    target = tmp_path / "pyproject.toml"
    target.write_text('description = "Harness-native 杩愯惀涓彴 Agent"\n', encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert "text:mojibake_marker_detected" in payload["files"][0]["missing_conditions"]


def test_production_landing_text_quality_check_allows_powershell_secret_guard_code(tmp_path: Path) -> None:
    target = tmp_path / "guard.ps1"
    target.write_text(
        "\n".join(
            [
                "$previousToken = [Environment]::GetEnvironmentVariable($tokenEnv, \"Process\")",
                "$skippedSecret = 0",
                "$plainToken = Convert-SecureStringToPlainText -SecureValue $secureToken",
                "if ($Value -match '(?i)(token|api[_-]?key|secret|password)\\s*[:=]') { throw 'looks like a secret' }",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")

    assert summary["status"] == "success"


def test_production_landing_text_quality_check_still_blocks_plain_secret_assignment(tmp_path: Path) -> None:
    target = tmp_path / "bad.ps1"
    target.write_text("$token = real-secret-token-value\n", encoding="utf-8")

    summary = build_production_landing_text_quality_check(targets=[target], output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert "text:secret_like_detected" in payload["files"][0]["missing_conditions"]
