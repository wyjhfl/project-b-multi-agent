from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.production_landing_real_llm_preflight_runner import (
    build_production_landing_real_llm_preflight_runner,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight"
XIAOMI_API_KEY_ENV = "XIAOMI_LLM_API_KEY"
XIAOMI_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
XIAOMI_MODEL = "mimo-v2.5-pro"


def build_production_landing_xiaomi_llm_preflight_runner(
    *,
    output_dir: str | Path | None = None,
    execute_network_check: bool = False,
    timeout_seconds: float = 20.0,
) -> dict:
    return build_production_landing_real_llm_preflight_runner(
        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
        execute_network_check=execute_network_check,
        timeout_seconds=timeout_seconds,
        provider="litellm",
        model=XIAOMI_MODEL,
        base_url=XIAOMI_BASE_URL,
        api_key_env=XIAOMI_API_KEY_ENV,
        provider_label="xiaomi",
        phase_label="v4.7 Xiaomi Real LLM Preflight Runner",
        report_stem="production_landing_xiaomi_llm_preflight",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Xiaomi OpenAI-compatible real LLM preflight without writing secrets to files."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute-network-check", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_xiaomi_llm_preflight_runner(
        output_dir=args.output_dir,
        execute_network_check=args.execute_network_check,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
