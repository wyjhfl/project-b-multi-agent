import sys
import json
import urllib.request
import urllib.error


BASE_URL = "http://localhost:8000"


def _get(path: str) -> dict | None:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        print(f"  FAIL {path}: {exc}")
        return None


def main():
    checks = [
        ("/health", "健康检查"),
        ("/tools", "工具列表"),
        ("/eval/summary", "评测汇总"),
        ("/observability/tasks/summary", "可观测汇总"),
    ]

    print("=== Project B: 健康检查 ===\n")
    all_ok = True

    for path, label in checks:
        print(f"  {label} ({path})...")
        data = _get(path)
        if data is not None:
            print(f"    OK")
        else:
            all_ok = False

    print()
    if all_ok:
        print("所有检查通过 ✓")
    else:
        print("部分检查失败 ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
