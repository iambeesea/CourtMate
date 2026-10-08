from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app import db as database
from app.db import Base
from app.migrate import run_migrations


def test_migrations_produce_exactly_the_modelled_schema(tmp_path):
    engine = database.configure(f"sqlite:///{tmp_path / 'migrated.db'}")
    run_migrations()
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        tables = set(inspect(connection).get_table_names())
    engine.dispose()
    assert differences == []
    assert set(Base.metadata.tables) <= tables


def test_migrations_can_be_reapplied_safely(tmp_path):
    engine = database.configure(f"sqlite:///{tmp_path / 'twice.db'}")
    run_migrations()
    run_migrations()
    engine.dispose()


def test_double_booking_guard_is_a_primary_key(tmp_path):
    engine = database.configure(f"sqlite:///{tmp_path / 'pk.db'}")
    run_migrations()
    with engine.connect() as connection:
        primary_key = inspect(connection).get_pk_constraint("reservation_slots")
    engine.dispose()
    assert primary_key["constrained_columns"] == ["unit_resource_id", "slot_start"]
