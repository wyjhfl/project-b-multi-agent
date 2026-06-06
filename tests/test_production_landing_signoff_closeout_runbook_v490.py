from __future__ import annotations

from pathlib import Path


def test_production_landing_signoff_closeout_runbook_documents_safe_closeout_flow() -> None:
    text = Path("docs/production_landing_signoff_closeout_runbook_v48.md").read_text(encoding="utf-8")

    assert "生产落地签核收口 Runbook" in text
    assert "scripts\\production_landing_signoff_closeout.ps1" in text
    assert "scripts/production_landing_signoff_closeout.py" in text
    assert "release_manager" in text
    assert "security_reviewer" in text
    assert "business_owner" in text
    assert "operations_owner" in text
    assert "YES" in text
    assert "manual_signoff_evidence_ack_status" in text
    assert "target_record_written=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "auto_signed=false" in text
    assert "auto_approved=false" in text
    assert "secret_plaintext_output=false" in text
    assert "tp-" not in text
    assert "sk-" not in text
