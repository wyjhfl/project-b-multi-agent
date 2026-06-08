from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


EXPECTED_TOKEN_ENV = "DEMO_BUSINESS_SYSTEM_TOKEN"


class Handler(BaseHTTPRequestHandler):
    server_version = "ProjectBDemoBusinessReadOnly/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/health":
            self._write(404, {"ok": False, "error": "not_found"})
            return
        expected_token = os.getenv(EXPECTED_TOKEN_ENV, "").strip()
        if not expected_token:
            self._write(503, {"ok": False, "error": "demo_token_not_configured"})
            return
        authorization = self.headers.get("Authorization", "").strip()
        api_key = self.headers.get("X-API-Key", "").strip()
        valid = authorization == f"Bearer {expected_token}" or api_key == expected_token
        if not valid:
            self._write(401, {"ok": False, "error": "read_only_token_required"})
            return
        self._write(
            200,
            {
                "status": "ok",
                "system": "demo_business_system",
                "environment": "controlled-demo",
                "readonly": True,
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        self._write(405, {"ok": False, "error": "write_methods_disabled"})

    def do_PUT(self) -> None:  # noqa: N802
        self._write(405, {"ok": False, "error": "write_methods_disabled"})

    def do_PATCH(self) -> None:  # noqa: N802
        self._write(405, {"ok": False, "error": "write_methods_disabled"})

    def do_DELETE(self) -> None:  # noqa: N802
        self._write(405, {"ok": False, "error": "write_methods_disabled"})

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _write(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    port = int(os.getenv("DEMO_BUSINESS_SYSTEM_PORT", "8876"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
