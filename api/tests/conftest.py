import datetime as dt
import os
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# Must be set before the application reads its settings.
os.environ.setdefault("SCRYPT_N", "1024")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("DEMO_LOGIN", "true")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import db as database  # noqa: E402
from app import seed  # noqa: E402
from app.main import app  # noqa: E402
from app.migrate import run_migrations  # noqa: E402
from app.models import Facility, Resource, User  # noqa: E402
from app.security import issue_token, rate_limiter  # noqa: E402

MANILA = ZoneInfo("Asia/Manila")
API = "/api/v1"


@pytest.fixture(scope="session")
def template_db(tmp_path_factory) -> Path:
    """A migrated, seeded SQLite file that each test copies. Built through Alembic, so migrations are exercised."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    from app.config import get_settings

    get_settings.cache_clear()
    engine = database.configure(f"sqlite:///{path}")
    run_migrations()
    with database.session_factory()() as session:
        seed.seed_reference(session, barangay_cities=seed.DEMO_CITY_CODES)
        seed.seed_demo(session)
    # Closing the last connection checkpoints the write-ahead log, leaving one self-contained file to copy.
    engine.dispose()
    return path


@pytest.fixture
def db_path(template_db: Path, tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    database.configure(f"sqlite:///{path}")
    rate_limiter.reset()
    yield path
    database.get_engine().dispose()


@pytest.fixture
def client(db_path: Path) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db(db_path: Path):
    with database.session_factory()() as session:
        yield session


def demo_headers(client: TestClient, persona: str = "player") -> dict[str, str]:
    response = client.post(f"{API}/auth/demo", json={"persona": persona})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def headers_for(email: str) -> dict[str, str]:
    """Issue a token straight from the database for a seeded user."""
    with database.session_factory()() as session:
        user = session.scalar(select(User).where(User.email == email))
        token, _ = issue_token(session, user)
        session.commit()
    return {"Authorization": f"Bearer {token}"}


def new_user(name: str = "Test Player") -> tuple[str, dict[str, str]]:
    """Create a user directly and return (id, auth headers)."""
    with database.session_factory()() as session:
        user = User(email=f"{name.lower().replace(' ', '.')}@example.com", display_name=name)
        session.add(user)
        session.flush()
        token, _ = issue_token(session, user)
        session.commit()
        return user.id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def player(client: TestClient) -> dict[str, str]:
    return demo_headers(client, "player")


@pytest.fixture
def operator(client: TestClient) -> dict[str, str]:
    return demo_headers(client, "operator")


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return demo_headers(client, "admin")


def scalar(statement):
    """Run one query in its own short-lived session.

    Prefer this to the `db` fixture between API calls: on SQLite an open session holds the write lock.
    """
    with database.session_factory()() as session:
        return session.scalar(statement)


def facility_named(name: str) -> Facility:
    with database.session_factory()() as session:
        return session.scalar(select(Facility).where(Facility.name == name))


def resource_named(facility_name: str, resource_name: str) -> Resource:
    with database.session_factory()() as session:
        return session.scalar(
            select(Resource)
            .join(Facility, Facility.id == Resource.facility_id)
            .where(Facility.name == facility_name, Resource.name == resource_name)
        )


def manila(days_ahead: int, hour: int, minute: int = 0) -> dt.datetime:
    """A wall-clock time in Manila `days_ahead` days from today."""
    day = dt.datetime.now(MANILA).date() + dt.timedelta(days=days_ahead)
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=MANILA)


def iso(value: dt.datetime) -> str:
    return value.isoformat()
