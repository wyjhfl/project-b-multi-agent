from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _assert_security_headers(headers) -> None:
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
    assert headers.get("X-XSS-Protection") == "0"


def test_health_has_security_headers():
    response = client.get("/health")
    assert response.status_code == 200
    _assert_security_headers(response.headers)


def test_deployment_check_has_security_headers():
    response = client.get("/deployment/check")
    assert response.status_code == 200
    _assert_security_headers(response.headers)


def test_cors_preflight_allows_localhost_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_rejects_unknown_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 400)
    assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"
