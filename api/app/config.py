import os
from dataclasses import dataclass, field
from functools import lru_cache


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./courtmate.db").strip()
    # Hosting providers hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=_database_url)
    cors_origins: list[str] = field(
        default_factory=lambda: [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()]
    )
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    # Demo data is clearly labelled wherever it is shown. Turn it off for a real launch.
    seed_demo_data: bool = field(default_factory=lambda: _flag("SEED_DEMO_DATA", True))
    demo_login: bool = field(default_factory=lambda: _flag("DEMO_LOGIN", _flag("SEED_DEMO_DATA", True)))
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
