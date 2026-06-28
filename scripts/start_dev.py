import subprocess
import sys


def main() -> None:
    print("=== Project B: initialize demo database ===")
    subprocess.check_call([sys.executable, "scripts/init_demo_db.py"])

    print("\n=== Project B: start backend dev server ===")
    print("Open http://localhost:8000/health to check service status")
    print("Press Ctrl+C to stop the service\n")
    subprocess.check_call([
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ])


if __name__ == "__main__":
    main()
