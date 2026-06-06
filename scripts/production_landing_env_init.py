from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.production_landing_env_template import DEFAULT_OUTPUT_PATH, build_production_landing_env_template

DEFAULT_ENV_PATH = ROOT_DIR / "local" / "production_landing.staging.env"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _is_gitignored_path(path: Path) -> bool:
    try:
        rel = str(path.resolve().relative_to(ROOT_DIR.resolve())).replace("\\", "/")
    except ValueError:
        return False
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def build_production_landing_env_init(
    *,
    env_path: str | Path | None = None,
    template_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    target = Path(env_path) if env_path else DEFAULT_ENV_PATH
    template = Path(template_path) if template_path else DEFAULT_OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    template_summary = build_production_landing_env_template(output_path=template)
    existed_before = target.exists()
    created = False
    overwritten = False
    if overwrite or not existed_before:
        text = template.read_text(encoding="utf-8")
        target.write_text(text, encoding="utf-8")
        created = not existed_before
        overwritten = existed_before and overwrite

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    gitignored = _is_gitignored_path(target)
    return {
        "status": "success" if gitignored else "partial",
        "generated_at": generated_at,
        "commit": commit,
        "env_path": str(target),
        "template_path": str(template),
        "env_file_present": target.exists(),
        "env_file_created": created,
        "env_file_existed_before": existed_before,
        "env_file_overwritten": overwritten,
        "gitignored": gitignored,
        "template_gitignored": bool(template_summary.get("gitignored", False)),
        "contains_real_secret": False,
        "secret_plaintext_output": False,
        "next_command": f"python scripts/production_landing_env_check.py --env-path {target}",
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize a local-only production landing env file.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--template-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_env_init(
        env_path=args.env_path,
        template_path=args.template_path,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
