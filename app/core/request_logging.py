from __future__ import annotations

import time
import uuid

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.structured_logging import build_log_event, emit_log_event


def _detect_result(status_code: int, payload: dict | None) -> str | None:
    if status_code == 429:
        return "rate_limited"
    if status_code == 413:
        return "request_too_large"
    if status_code in {400, 414}:
        return "request_rejected"
    if payload and isinstance(payload.get("error"), str):
        return payload["error"]
    return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        result: str | None = None
        error_type: str | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            result = _detect_result(status_code, None)
            if status_code >= 400:
                error_type = f"http_{status_code}"
            return response
        except Exception as exc:  # pragma: no cover
            status_code = 500
            error_type = type(exc).__name__
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_server_error"},
                headers={"X-Request-ID": request_id},
            )
            return response
        finally:
            if not settings.structured_logging_enabled:
                return
            latency_ms = (time.perf_counter() - started) * 1000
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "")
            actor = getattr(request.state, "actor", None) or "anonymous"
            log_event = build_log_event(
                event_type="http_request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=latency_ms,
                actor=actor,
                client_ip=client_ip,
                user_agent=user_agent,
                error_type=error_type,
                result=result,
            )
            emit_log_event(log_event)
