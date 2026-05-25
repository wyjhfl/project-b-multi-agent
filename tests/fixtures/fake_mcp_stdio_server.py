from __future__ import annotations

import json
import sys
import time


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if mode == "crash":
        return 2

    line = sys.stdin.readline()
    if not line:
        return 0

    if mode == "no-response":
        time.sleep(2.0)
        return 0

    if mode == "invalid-json":
        sys.stdout.write("{invalid-json}\n")
        sys.stdout.flush()
        return 0

    try:
        req = json.loads(line)
    except Exception:
        _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        return 0

    req_id = req.get("id")
    method = req.get("method")
    if method == "initialize":
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "serverInfo": {"name": "fake-mcp-stdio", "version": "0.1.0"},
                    "capabilities": {},
                },
            }
        )
        return 0

    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method: {method}"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
