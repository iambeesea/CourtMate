# CourtMate

CourtMate is a mobile-first sports platform for the Philippines. Players discover open plays, reserve courts, fields, lanes, tables and studios, join sessions and live queues, play with their communities, and keep a record for every sport they play.

**Discover a sport → find a venue or open play → reserve or join → play → track results → share → play again.**

## What it does

- **30 sports, one system.** Racket and paddle, team and court, bat and field, indoor, fitness and outdoor sports each carry their own configuration: formats, session types, scoring, resources and queue rules. Administrators add sports without a code change.
- **Venues and bookings.** Day-by-day availability, weekly series, full and half resources, and booking rules per venue. The database, not the application, refuses a double booking.
- **Open plays.** Host or join sessions with capacity, waitlists that promote in order, optional host approval, and live queues with rotation or winner-stays.
- **Philippine locations.** Region, province, city or municipality and barangay from the Philippine Standard Geographic Code, plus "near me" search and a map.
- **Communities and teams.**
- **Player records** computed from recorded matches, logged activities and checked-in attendance. Nothing is estimated. Any record can be shared as an Instagram Story card.
- **Venue dashboard** for operators: spaces, hours, prices, blocks, booking requests, cancellations and occupancy. Venues are verified before they are listed.
- **Installable** as a progressive web app.

All schedules are shown in Philippine time.

## Demo data

A fresh install loads clearly labelled demo venues, sessions, communities and results so every screen has something to show. None of it describes a real venue, price or schedule. "Sign in → Demo player" needs no password. Set `SEED_DEMO_DATA=false` and `DEMO_LOGIN=false` for a real launch.

## Run it locally

Requirements: Node 22 or newer, and [uv](https://docs.astral.sh/uv/) (which provides Python 3.12).

```bash
# Terminal 1 — API on http://localhost:8000 (interactive docs at /docs)
cd api
uv sync
uv run fastapi dev

# Terminal 2 — web on http://localhost:5173
cd web
npm install
npm run dev
```

The API creates a local SQLite database on first start.

## Checks

```bash
cd api && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd web && npm run lint && npm test && npm run build
```

The same checks run in GitHub Actions on every pull request (`.github/workflows/ci.yml`).

## Brand palette

| | |
| --- | --- |
| White | `#FFFFFF` |
| Light Gray | `#E8E8E8` |
| Court Navy | `#1F3B73` |
| Rally Lime | `#E0FE2C` |

## Stack

- Web: React 19, TypeScript, Vite, React Router, Leaflet
- API: FastAPI, SQLAlchemy 2, Alembic, Pydantic; SQLite for development, PostgreSQL for production
- Hosting: Vercel (web) and Render (API)

## Documentation

| Document | Contents |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How sports, venues, bookings, sessions, locations and records are modelled |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | What each phase delivered, test results and known limitations |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Environment variables, database, first administrator, going live |
| [docs/AUDIT.md](docs/AUDIT.md) | The state of the original MVP and the defects found in it |
| [CHANGELOG.md](CHANGELOG.md) | Changes by phase |
| [api/README.md](api/README.md) | API layout, migrations and commands |
| [api/app/data/psgc/SOURCE.md](api/app/data/psgc/SOURCE.md) | Where the location data comes from and its gaps |
