# CourtMate API

FastAPI + SQLAlchemy. See `../docs/ARCHITECTURE.md` for the design and `../docs/IMPLEMENTATION.md` for status.

## Run

```bash
uv sync                # creates .venv with Python 3.12
uv run fastapi dev     # http://localhost:8000, interactive docs at /docs
```

On start the API applies database migrations, loads the sport catalog and the Philippine location data, and (unless `SEED_DEMO_DATA=false`) loads clearly labelled demo data. With no `DATABASE_URL` it uses a local SQLite file, `courtmate.db`.

## Check

```bash
uv run pytest          # API tests, including a concurrent double-booking race
uv run ruff check .
uv run ruff format --check .
```

## Database migrations

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

`tests/test_migrations.py` fails if the migrations and the models drift apart.

## Layout

| Path | Contents |
| --- | --- |
| `app/models.py` | Tables and constraints |
| `app/schemas.py` | Request and response shapes |
| `app/serializers.py` | What leaves the API (privacy decisions live here) |
| `app/services/` | Booking engine and other domain logic |
| `app/routers/` | HTTP routes |
| `app/sports_catalog.py` | Initial sport catalog (data) |
| `app/seed.py` | Reference data and demo data |
| `app/data/psgc/` | Philippine Standard Geographic Code seed files |
| `migrations/` | Alembic revisions |
| `scripts/build_psgc.py` | Rebuilds the location seed files |
