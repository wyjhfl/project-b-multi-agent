from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], description: str) -> None:
    print(f"[start_app] {description}: {' '.join(command)}", flush=True)
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"[start_app] {description} failed with exit code {result.returncode}", file=sys.stderr, flush=True)
        raise SystemExit(result.returncode)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    _run([sys.executable, str(root / "scripts" / "init_demo_db.py")], "initialize demo database")

    storage_backend = os.environ.get("STORAGE_BACKEND", "sqlite").lower()
    database_url = os.environ.get("DATABASE_URL", "")
    if storage_backend == "postgres" and database_url:
        _run([sys.executable, "-m", "alembic", "upgrade", "head"], "alembic upgrade head")

    _run([
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ], "start uvicorn")


if __name__ == "__main__":
    main()
