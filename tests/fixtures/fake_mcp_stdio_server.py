from __future__ import annotations

import json
import sys
import time
from typing import Any


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _tools_payload() -> list[dict[str, Any]]:
    return [
        {
            "name": "stdio_date_lookup",
            "description": "Return current date",
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "month": {"type": "integer"},
                    "year": {"type": "integer"},
                },
            },
            "riskLevel": "low",
            "permissionScope": "read",
        },
        {
            "name": "stdio_refund_update",
            "description": "Update refund status",
            "inputSchema": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}, "status": {"type": "string"}},
                "required": ["order_id", "status"],
            },
            "outputSchema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            "riskLevel": "high",
            "permissionScope": "write",
        },
        {
            "name": "stdio_default_policy_tool",
            "description": "Missing risk and permission to test defaults",
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
        {
            "name": "",
            "description": "invalid tool should be skipped",
        },
    ]


def _handle_request(mode: str, req: dict[str, Any]) -> bool:
    req_id = req.get("id")
    method = req.get("method")

    if mode == "invalid-json":
        sys.stdout.write("{invalid-json}\n")
        sys.stdout.flush()
        return False
    if mode == "no-response":
        time.sleep(2.0)
        return False
    if mode == "crash":
        raise RuntimeError("server crashed")

    if method == "initialize":
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "serverInfo": {"name": "fake-mcp-stdio", "version": "0.2.0"},
                    "capabilities": {},
                },
            }
        )
        return True

    if method == "tools/list":
        if mode == "tools-list-bad-structure":
            _write({"jsonrpc": "2.0", "id": req_id, "result": {"tools": "not-a-list"}})
            return True
        if mode == "tools-list-direct-list":
            _write({"jsonrpc": "2.0", "id": req_id, "result": _tools_payload()})
            return True
        _write({"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tools_payload()}})
        return True

    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method: {method}"}})
    return True


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if mode == "crash":
        return 2

    while True:
        line = sys.stdin.readline()
        if not line:
            return 0
        try:
            req = json.loads(line)
        except Exception:
            _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue

        try:
            keep_running = _handle_request(mode, req)
        except Exception:
            return 2
        if not keep_running:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
