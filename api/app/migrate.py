from pathlib import Path

from alembic import command
from alembic.config import Config

API_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    return config


def run_migrations() -> None:
    """Bring the configured database up to the latest schema revision."""
    command.upgrade(alembic_config(), "head")
