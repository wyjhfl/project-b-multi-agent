from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    server_version = "ProjectBLocalBusinessMock/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/health":
            self._write(404, {"ok": False, "error": "not_found"})
            return
        auth_present = bool(self.headers.get("Authorization", "").strip())
        if not auth_present:
            self._write(401, {"ok": False, "error": "authorization_missing"})
            return
        self._write(200, {"ok": True, "service": "local-business-read-mock", "read_only": True})

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
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
