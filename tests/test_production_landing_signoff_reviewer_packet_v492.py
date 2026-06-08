from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_signoff_reviewer_packet import build_production_landing_signoff_reviewer_packet


def _write_report(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sources(root: Path) -> dict[str, tuple[Path, str]]:
    return {
        "pre_signoff_gate": (root / "pre", "*.json"),
        "action_pack": (root / "action", "*.json"),
        "final_verification": (root / "final", "*.json"),
        "manual_signoff_evidence_ack_status": (root / "ack", "*.json"),
        "real_llm_preflight": (root / "real_llm", "*.json"),
        "xiaomi_llm_preflight": (root / "llm", "*.json"),
        "real_integration_staging_smoke": (root / "staging", "*.json"),
        "business_system_read_smoke": (root / "business", "*.json"),
        "signoff_closeout": (root / "closeout", "*.json"),
    }


def _write_ready_reports(root: Path) -> None:
    _write_report(
        root / "pre",
        "001.json",
        {
            "status": "ready_for_manual_signoff",
            "ready_for_manual_signoff": True,
            "technical_evidence_ready": True,
            "non_signoff_blocker_count": 0,
            "ack_ready": True,
            "secret_plaintext_output": False,
        },
    )
    _write_report(root / "action", "001.json", {"status": "partial", "required_input_count": 1})
    _write_report(root / "final", "001.json", {"status": "partial", "passed_count": 5, "requirement_count": 9})
    _write_report(root / "ack", "001.json", {"status": "success", "recommended_accept_count": 4, "item_count": 4})
    _write_report(
        root / "real_llm",
        "001.json",
        {
            "status": "success",
            "api_key_present": True,
            "network_check_executed": True,
            "real_llm_executed": True,
            "source": "generic",
        },
    )
    _write_report(root / "llm", "001.json", {"status": "success", "api_key_present": True, "network_check_executed": True, "real_llm_executed": True})
    _write_report(root / "staging", "001.json", {"status": "success", "database_connected": True, "redis_connected": True, "external_mcp_connected": True})
    _write_report(root / "business", "001.json", {"status": "success", "business_system_connected": True, "business_read_executed": True, "business_write_executed": False})
    _write_report(root / "closeout", "001.json", {"status": "partial", "target_record_written": False, "missing_conditions": ["manual_signoff:not_completed"]})


def test_signoff_reviewer_packet_ready_for_review(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_ready_reports(root)

    summary = build_production_landing_signoff_reviewer_packet(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready_for_review"
    assert summary["ready_for_manual_signoff"] is True
    assert payload["technical_evidence_ready"] is True
    assert payload["non_signoff_blocker_count"] == 0
    assert payload["manual_ack"]["recommended_accept_count"] == 4
    assert payload["real_llm_preflight"]["source_id"] == "real_llm_preflight"
    assert payload["real_llm_preflight"]["compat_fallback_used"] is False
    assert payload["real_llm_preflight"]["real_llm_executed"] is True
    assert payload["staging_smoke"]["database_connected"] is True
    assert payload["business_read_smoke"]["business_write_executed"] is False
    assert payload["recommended_closeout_command"].endswith("scripts\\production_landing_signoff_closeout.ps1")
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_signoff_reviewer_packet_reads_nested_generic_preflight_network_flag(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_ready_reports(root)
    _write_report(
        root / "real_llm",
        "002.json",
        {
            "generated_at": "2026-06-07T00:00:00+00:00",
            "status": "success",
            "api_key_present": True,
            "preflight": {"network_check_executed": True},
            "real_llm_executed": True,
        },
    )

    summary = build_production_landing_signoff_reviewer_packet(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert payload["real_llm_preflight"]["source_id"] == "real_llm_preflight"
    assert payload["real_llm_preflight"]["network_check_executed"] is True
    assert payload["real_llm_preflight"]["real_llm_executed"] is True


def test_signoff_reviewer_packet_falls_back_to_xiaomi_when_generic_missing(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_ready_reports(root)
    for path in (root / "real_llm").glob("*.json"):
        path.unlink()

    summary = build_production_landing_signoff_reviewer_packet(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready_for_review"
    assert payload["real_llm_preflight"]["source_id"] == "xiaomi_llm_preflight"
    assert payload["real_llm_preflight"]["compat_fallback_used"] is True
    assert not any(item == "real_llm_preflight:report_not_found" for item in payload["missing_conditions"])


def test_signoff_reviewer_packet_partial_when_evidence_missing(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_report(root / "pre", "001.json", {"status": "partial", "ready_for_manual_signoff": False})

    summary = build_production_landing_signoff_reviewer_packet(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["ready_for_manual_signoff"] is False
    assert payload["missing_condition_count"] >= 1
    assert any(item.endswith("report_not_found") for item in payload["missing_conditions"])


def test_signoff_reviewer_packet_blocks_secret_like_content_without_leaking_value(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_ready_reports(root)
    _write_report(root / "closeout", "002.json", {"status": "partial", "note": "token=sk-should-not-leak"})

    summary = build_production_landing_signoff_reviewer_packet(output_dir=tmp_path / "out", sources=_sources(root))
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert "sk-should-not-leak" not in merged
