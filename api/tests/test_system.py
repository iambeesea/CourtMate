from .conftest import API


def test_health_and_root(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").json()["name"] == "CourtMate API"


def test_config_reports_demo_mode_and_timezone(client):
    body = client.get(f"{API}/config").json()
    assert body["demoLogin"] is True
    assert body["defaultTimezone"] == "Asia/Manila"
    assert body["bookingQuantumMinutes"] == 15


def test_security_headers_are_set(client):
    response = client.get(f"{API}/sports")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_the_configured_origin_only(client):
    allowed = client.options(f"{API}/sports", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in allowed.headers
    denied = client.options(f"{API}/sports", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_schema_builds(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert f"{API}/reservations" in paths
