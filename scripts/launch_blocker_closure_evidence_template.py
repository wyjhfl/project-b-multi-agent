from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure" / "closure_evidence.template.json"


def _load_register(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("launch blocker register must be a JSON object")
    return payload


def build_launch_blocker_closure_evidence_template(
    *,
    launch_blockers: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    source = _load_register(launch_blockers)
    blockers = source.get("blocker_register") if isinstance(source.get("blocker_register"), list) else []
    output = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for item in blockers:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "blocker_id": str(item.get("blocker_id") or ""),
                "source_key": str(item.get("source_key") or ""),
                "owner": "manual_owner_required",
                "due_at": "manual_due_date_required",
                "compensating_controls": ["manual_compensating_controls_required"],
                "closure_evidence_refs": ["manual_closure_evidence_required"],
                "reviewer": "",
                "approval_state": "not_approved",
                "notes": [
                    "填写脱敏证据引用，不要写入 token、API key、连接串、客户敏感数据或未脱敏日志。",
                    "approval_state 可在人工复核后改为 pending_review 或 approved；模板默认 not_approved，不会自动关闭 blocker。",
                ],
            }
        )
    payload = {
        "status": "partial",
        "read_only": True,
        "auto_approved": False,
        "auto_closed": False,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "closure_items": rows,
        "closure_item_count": len(rows),
        "source_register": str(Path(launch_blockers)),
        "public_production_direct_launch": "No-Go",
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "success",
        "template_path": str(output),
        "closure_item_count": len(rows),
        "auto_approved": False,
        "auto_closed": False,
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 launch blocker closure evidence JSON 填写模板。")
    parser.add_argument("--launch-blockers", required=True)
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_launch_blocker_closure_evidence_template(
        launch_blockers=args.launch_blockers,
        output_path=args.output_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
