import os
from dataclasses import dataclass, field
from functools import lru_cache


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    # An empty value (an unfilled dashboard field) means "not set".
    url = (os.getenv("DATABASE_URL") or "").strip() or "sqlite:///./courtmate.db"
    # Hosting providers hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def _environment() -> str:
    # "Production" or " production " typed into a dashboard must still count as production.
    return (os.getenv("ENVIRONMENT") or "development").strip().lower()


def _origins(value: str) -> list[str]:
    # Browsers send an origin with no trailing slash, so "https://site.app/" would never match.
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip().rstrip("/")]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=_database_url)
    cors_origins: list[str] = field(default_factory=lambda: _origins(os.getenv("CORS_ORIGINS") or "http://localhost:5173"))
    environment: str = field(default_factory=lambda: _environment())
    # Demo data is clearly labelled wherever it is shown. Turn it off for a real launch.
    seed_demo_data: bool = field(default_factory=lambda: _flag("SEED_DEMO_DATA", True))
    demo_login: bool = field(default_factory=lambda: _flag("DEMO_LOGIN", _flag("SEED_DEMO_DATA", True)))
    # The demo administrator can change the sport catalog and verify venues, so on a
    # production deployment it stays off unless it is switched on deliberately.
    demo_admin_login: bool = field(default_factory=lambda: _flag("DEMO_ADMIN_LOGIN", _environment() != "production"))
    max_body_bytes: int = field(default_factory=lambda: int(os.getenv("MAX_BODY_BYTES", str(256 * 1024))))
    auto_migrate: bool = field(default_factory=lambda: _flag("AUTO_MIGRATE", True))
    rate_limit_enabled: bool = field(default_factory=lambda: _flag("RATE_LIMIT_ENABLED", True))
    token_ttl_hours: int = field(default_factory=lambda: int(os.getenv("TOKEN_TTL_HOURS", str(24 * 14))))
    scrypt_n: int = field(default_factory=lambda: int(os.getenv("SCRYPT_N", str(2**15))))

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
