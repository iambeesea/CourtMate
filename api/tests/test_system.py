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


def test_oversized_bodies_are_refused(client):
    huge = "x" * (300 * 1024)
    response = client.post(f"{API}/auth/login", json={"email": "a@example.com", "password": huge})
    assert response.status_code == 413


def test_large_responses_are_compressed(client):
    response = client.get(f"{API}/sports", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
    assert len(response.json()) == 30


def test_demo_admin_flag_is_reported(client):
    assert client.get(f"{API}/config").json()["demoAdminLogin"] is True


def test_database_url_handling(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("DATABASE_URL", "")
    assert Settings().database_url == "sqlite:///./courtmate.db"
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.internal:5432/courtmate")
    assert Settings().database_url == "postgresql+psycopg://user:secret@db.internal:5432/courtmate"
    assert Settings().is_sqlite is False


def test_every_state_changing_route_requires_sign_in():
    """A guard against adding a write route and forgetting its permission check."""
    from fastapi.routing import APIRoute

    from app import routers
    from app.security import current_user, require_admin

    def dependencies(dependant, seen=None):
        seen = set() if seen is None else seen
        for sub in dependant.dependencies:
            if sub.call not in seen:
                seen.add(sub.call)
                dependencies(sub, seen)
        return seen

    names = (
        "admin",
        "auth",
        "communities",
        "facilities",
        "geo",
        "notifications",
        "operator",
        "players",
        "reservations",
        "sessions",
        "sports",
        "teams",
    )
    open_writes, count = set(), 0
    for name in names:
        module = __import__(f"{routers.__name__}.{name}", fromlist=["router"])
        for route in module.router.routes:
            if not isinstance(route, APIRoute):
                continue
            count += 1
            used = dependencies(route.dependant)
            if name == "admin":
                assert require_admin in used, route.path
            if name == "operator":
                assert current_user in used, route.path
            if route.methods & {"POST", "PATCH", "PUT", "DELETE"} and current_user not in used and require_admin not in used:
                open_writes.add(route.path)
    assert count >= 80
    assert open_writes == {"/auth/register", "/auth/login", "/auth/demo", "/auth/logout"}


def test_cors_origins_tolerate_trailing_slashes_and_spaces(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", " https://courtmate.example/ , http://localhost:5173,, ")
    assert Settings().cors_origins == ["https://courtmate.example", "http://localhost:5173"]
    monkeypatch.setenv("CORS_ORIGINS", "")
    assert Settings().cors_origins == ["http://localhost:5173"]
