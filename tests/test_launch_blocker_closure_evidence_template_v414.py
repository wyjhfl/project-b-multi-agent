from __future__ import annotations

import json
from pathlib import Path

from scripts.launch_blocker_closure_evidence_template import build_launch_blocker_closure_evidence_template


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_launch_blocker_closure_evidence_template_is_not_preapproved(tmp_path: Path) -> None:
    register = tmp_path / "launch_blockers.json"
    _write_json(
        register,
        {
            "status": "partial",
            "read_only": True,
            "blocker_register": [
                {"blocker_id": "LB-001", "source_key": "business_system_integration_acceptance_missing"},
                {"blocker_id": "LB-002", "source_key": "manual_signoff_missing"},
            ],
        },
    )

    summary = build_launch_blocker_closure_evidence_template(
        launch_blockers=register,
        output_path=tmp_path / "closure_evidence.template.json",
    )
    payload = json.loads(Path(summary["template_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "success"
    assert summary["closure_item_count"] == 2
    assert payload["read_only"] is True
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert {item["approval_state"] for item in payload["closure_items"]} == {"not_approved"}
    assert {item["owner"] for item in payload["closure_items"]} == {"manual_owner_required"}
    assert "manual_closure_evidence_required" in payload["closure_items"][0]["closure_evidence_refs"]
    merged = Path(summary["template_path"]).read_text(encoding="utf-8")
    assert "sk-" not in merged
    assert "bearer " not in merged.lower()
