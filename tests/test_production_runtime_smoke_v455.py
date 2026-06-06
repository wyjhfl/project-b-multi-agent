from __future__ import annotations

import json
from pathlib import Path

from scripts.production_runtime_smoke import build_production_runtime_smoke


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_runtime_smoke_generates_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_PRODUCTION_BUILD_REPORT_DIR", str(tmp_path / "missing_frontend_build"))
    monkeypatch.setenv("PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR", str(tmp_path / "missing_bootstrap"))

    summary = build_production_runtime_smoke(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "success"
    assert payload["mode"] == "in_process_runtime_smoke"
    assert summary["endpoint_check_count"] == 3
    assert all(item["passed"] is True for item in payload["endpoint_checks"])
    assert payload["operations_contract"]["health_status"] == "ok"
    assert payload["operations_contract"]["public_production_direct_launch"] == "No-Go"
    assert payload["real_llm_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert Path(summary["markdown_path"]).exists()


def test_production_runtime_smoke_blocks_when_operations_contract_is_unsafe(tmp_path: Path, monkeypatch) -> None:
    from scripts import production_runtime_smoke as module

    monkeypatch.setattr(
        module,
        "_collect_endpoint_checks",
        lambda: [
            {"path": "/health", "http_status": 200, "passed": True, "response_json_present": True},
            {"path": "/operations/summary", "http_status": 200, "passed": True, "response_json_present": True},
            {"path": "/deployment/check", "http_status": 200, "passed": True, "response_json_present": True},
        ],
    )
    monkeypatch.setattr(
        module,
        "_collect_operations_contract",
        lambda: {
            "status": "blocked",
            "missing_conditions": ["operations_summary:bootstrap_public_launch_not_no_go"],
            "health_status": "ok",
            "public_production_direct_launch": "No-Go",
            "business_system_connected": False,
        },
    )

    summary = module.build_production_runtime_smoke(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert "operations_summary:bootstrap_public_launch_not_no_go" in payload["operations_contract"]["missing_conditions"]
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_production_runtime_smoke_fails_when_endpoint_fails(tmp_path: Path, monkeypatch) -> None:
    from scripts import production_runtime_smoke as module

    monkeypatch.setattr(
        module,
        "_collect_endpoint_checks",
        lambda: [{"path": "/health", "http_status": 500, "passed": False, "response_json_present": True}],
    )
    monkeypatch.setattr(
        module,
        "_collect_operations_contract",
        lambda: {"status": "success", "health_status": "ok", "business_system_connected": False},
    )

    summary = module.build_production_runtime_smoke(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "failed"


def test_production_runtime_smoke_does_not_leak_secret_like_text(tmp_path: Path, monkeypatch) -> None:
    from scripts import production_runtime_smoke as module

    monkeypatch.setattr(module, "_run_git", lambda args: "token=sk-should-not-leak")

    summary = module.build_production_runtime_smoke(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "sk-should-not-leak" not in merged
    assert summary["commit"] == "redacted"
