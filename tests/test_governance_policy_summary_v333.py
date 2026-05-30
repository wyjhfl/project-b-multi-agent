from __future__ import annotations

import json
from pathlib import Path

from scripts.governance_policy_summary import build_governance_policy_summary


def test_governance_policy_summary_generates_json_and_markdown(tmp_path: Path):
    summary = build_governance_policy_summary(output_dir=tmp_path / "out")
    json_path = Path(summary["json_path"])
    md_path = Path(summary["markdown_path"])

    assert summary["status"] == "ok"
    assert summary["read_only"] is True
    assert summary["policy_count"] >= 10
    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["generated_at"]
    assert payload["commit"]
    assert payload["real_llm_executed"] is False
    assert payload["read_only"] is True
    assert isinstance(payload["policy_items"], list)


def test_governance_policy_summary_contains_required_boundaries(tmp_path: Path):
    summary = build_governance_policy_summary(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    boundaries = payload.get("boundary_declarations", [])
    merged = "\n".join(boundaries)

    required_tokens = [
        "default fake/offline",
        "default pytest/CI no real LLM",
        "real LLM opt-in only; missing env => skipped",
        "no secret plaintext commit",
        "OIDC minimal drill boundary preserved",
        "report retention read-only boundary preserved",
        "config drift read-only boundary preserved",
        "history tag immutability boundary preserved",
        "no public production direct launch claim",
    ]
    for token in required_tokens:
        assert token in merged


def test_governance_policy_summary_no_secret_leak(tmp_path: Path):
    summary = build_governance_policy_summary(output_dir=tmp_path / "out")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    forbidden = [
        "sk-",
        "client_secret=",
        "JWT_SECRET=",
        "DATABASE_URL=",
        "REDIS_URL=",
        "postgresql://",
        "redis://:",
        "raw_prompt",
    ]
    for text in forbidden:
        assert text not in merged


def test_governance_policy_summary_is_read_only(tmp_path: Path):
    summary = build_governance_policy_summary(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
