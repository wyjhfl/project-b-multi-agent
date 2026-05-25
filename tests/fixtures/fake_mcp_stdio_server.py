from __future__ import annotations

import json
import os
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
                "properties": {"refund_id": {"type": "string"}, "status": {"type": "string"}},
                "required": ["refund_id"],
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
        time.sleep(1.0)
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

    if method == "tools/call":
        if mode == "tool-error":
            _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32010, "message": "tool call failed"}})
            return True
        if mode == "malformed-result":
            _write({"jsonrpc": "2.0", "id": req_id, "result": ["malformed", "result"]})
            return True
        params = req.get("params") or {}
        if not isinstance(params, dict):
            _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "invalid params"}})
            return True
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        if name == "stdio_date_lookup":
            _write({"jsonrpc": "2.0", "id": req_id, "result": {"date": "2026-05-25", "source": "stdio"}})
            return True
        if name == "stdio_refund_update":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"updated": True, "refund_id": arguments.get("refund_id", "")},
                }
            )
            return True
        _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown tool: {name}"}})
        return True

    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method: {method}"}})
    return True


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
    state_file = sys.argv[2] if len(sys.argv) > 2 else ""
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
            if mode == "stderr-crash":
                sys.stderr.write("fatal stderr crash marker\n")
                sys.stderr.flush()
                return 2
            if mode == "once-crash-then-normal" and state_file and not os.path.exists(state_file):
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write("crashed_once")
                return 2
            if mode == "timeout-once-then-normal" and state_file and not os.path.exists(state_file):
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write("timed_out_once")
                time.sleep(1.0)
                continue
            keep_running = _handle_request(mode, req)
        except Exception:
            return 2
        if not keep_running:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
