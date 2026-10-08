# Implementation status

Branch `feat/courtmate-multisport`. Updated at the end of each phase. Design is in `ARCHITECTURE.md`; the starting point is in `AUDIT.md`.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | GitHub connection, audit, architecture | Done |
| 2 | Universal sports foundation | Done |
| 3 | Open plays | Not started |
| 4 | Communities and statistics | Not started |
| 5 | Facility management | Not started |
| 6 | Mobile and production | Not started |

## Phase 2 — Universal sports foundation

**API**

- SQLAlchemy 2 models for the whole platform with Alembic migrations (29 tables). SQLite locally, PostgreSQL through `DATABASE_URL`.
- Sport catalog: 30 sports in 6 categories, each with its own player, match, scoring and resource configuration. Admins add and edit sports through the API.
- Philippine locations from the PSGC: 17 regions, 81 provinces, 1,634 cities and municipalities, 42,046 barangays.
- Accounts: registration, sign-in, sign-out, profile with per-sport skill levels. scrypt password hashes, revocable opaque tokens stored as digests, rate-limited sign-in.
- Facilities and resources with opening hours, parent/child resources, booking rules, and location and distance search.
- Availability per day and reservations with database-enforced double-booking prevention, weekly series, cancellation and late-cancellation tracking.
- Six demo facilities covering courts, half courts, fields, lanes, tables, a pool with lanes, studios, a climbing wall and tee times. All are labelled demo.

**Web**

- React Router with a shared shell: Explore, Bookings, Play, Profile.
- Sport picker driven by the catalog, with categories.
- Location picker: region → province → city or municipality → barangay, or a radius around the device's location.
- Venue list and map (Leaflet, loaded on demand), venue page with a 14-day availability calendar, slot selection and booking.
- Bookings page with upcoming and past reservations and cancellation.
- Sign in, create account, demo sign-in, profile editing.
- All times render in Philippine time whatever the device's time zone.

**Still served by the original MVP code in this phase**: the open-session list, "Play" (my sessions) and the player record. They are replaced in phases 3 and 4.

## How to run

```bash
# Terminal 1
cd api && uv sync && uv run fastapi dev

# Terminal 2
cd web && npm install && npm run dev
```

Open <http://localhost:5173>. "Sign in → Demo player" needs no password.

## Checks

| Check | Command | Result at the end of phase 2 |
| --- | --- | --- |
| API tests | `cd api && uv run pytest` | 78 passed |
| API lint and format | `uv run ruff check . && uv run ruff format --check .` | Clean |
| Web type check and build | `cd web && npm run build` | Clean |
| Web lint | `npm run lint` | Clean |
| Web unit tests | `npm test` | 9 passed (also with `TZ=America/New_York`) |
| Browser walk-through | Explore → venue → pick slots → demo sign-in → confirm → Bookings; location filter on a phone-sized viewport | Worked |

## Known limitations

- **PostgreSQL has not been exercised.** Every test and manual check ran on SQLite. The schema and the booking guard use only portable features, and the PostgreSQL driver is installed, but the first PostgreSQL deployment should be treated as untested.
- **Location data is an older PSGC snapshot** (17 regions, 81 provinces). See `api/app/data/psgc/SOURCE.md`.
- **Email addresses are not verified** and there is no password reset. Both need an email provider.
- **Access tokens are kept in `localStorage`.** That is simple and works across the separate web and API hosts, but any script injected into the page could read the token. Moving the API behind the web origin and using an HttpOnly cookie is the stronger setup.
- **Rate limiting is per process** and keyed on the connecting address. Behind a proxy the API needs forwarded headers enabled to see real client addresses, and more than one instance needs a shared store.
- **No online payments.** Reservations record "pay at venue".
- **Opening hours cannot cross midnight**, and each weekday has a single opening period.
- **Bookings use 15-minute steps**, so tee times at 10-minute intervals are not representable.
- **SQLite serialises all database access.** Fine for development and the demo; production traffic should use PostgreSQL.
- **OpenStreetMap's public tile server** is used for maps. It is meant for light use; set `VITE_MAP_TILE_URL` to a tile provider for production.
- **Distance search computes distances in the application** after a bounding-box filter. That is fine for thousands of venues; a spatial index is the next step beyond that.
