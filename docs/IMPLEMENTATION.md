# Implementation status

Branch `feat/courtmate-multisport`. Updated at the end of each phase. Design is in `ARCHITECTURE.md`; the starting point is in `AUDIT.md`.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | GitHub connection, audit, architecture | Done |
| 2 | Universal sports foundation | Done |
| 3 | Open plays | Done |
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

## Phase 3 — Open plays

**API**

- `play_sessions` replace the in-memory session list. One model covers open play, pickup games, classes, sparring, group runs and rides, tee times and events; each sport's configuration decides which kinds, formats, skill levels and queue modes it allows.
- Discovery (`GET /api/v1/sessions`) by sport, category, kind, region, province, city, barangay, facility, time window, skill level, fee, open places, text, and distance.
- Join and leave per player. Capacity is an atomic conditional update backed by a `CHECK` constraint. Full sessions waitlist; a vacated place passes to the first waitlisted player, who is notified.
- Approval sessions hold joiners as pending for the host. Hosts approve, decline, remove, check players in, edit, reschedule (players are notified), start, finish and cancel.
- Hosting can reserve a venue resource in the same transaction; if the venue is taken, no session is created. Cancelling the session releases the booking.
- Live queues for queue-eligible sports: check-in, waiting line, rest and rejoin, `rotation` and `winner_stays` modes, calling the next match onto a free court, recording a score validated against the sport's scoring rules, voiding a match.
- Thirteen demo sessions across eleven sports plus one live demo queue. Demo sessions renew themselves on a database that outlives them.

**Web**

- Explore lists real sessions with time, open-places and free filters, and shows them on the map beside venues.
- Session page: details, join/leave/waitlist/request, people lists, host controls, and the live queue with score entry shaped by the sport (games, totals, or result).
- Host form driven by the sport's configuration: a running session asks for a meet-up point and route; a badminton session asks for format, venue and queue.
- Play tab: live sessions first, then joined and hosted sessions, upcoming and past.

**Still served by the original MVP code in this phase**: the player record and the communities endpoint. They are replaced in phase 4.

## How to run

```bash
# Terminal 1
cd api && uv sync && uv run fastapi dev

# Terminal 2
cd web && npm install && npm run dev
```

Open <http://localhost:5173>. "Sign in → Demo player" needs no password.

## Checks

| Check | Command | Latest result (end of phase 3) |
| --- | --- | --- |
| API tests | `cd api && uv run pytest` | 113 passed |
| API lint and format | `uv run ruff check . && uv run ruff format --check .` | Clean |
| Web type check and build | `cd web && npm run build` | Clean |
| Web lint | `npm run lint` | Clean |
| Web unit tests | `npm test` | 9 passed (also with `TZ=America/New_York`) |
| Browser walk-through | Explore → venue → pick slots → demo sign-in → confirm → Bookings; location filter on a phone-sized viewport; session page → check in to the live queue; host form for running and badminton | Worked |

## Known limitations

- **PostgreSQL has not been exercised.** Every test and manual check ran on SQLite. The schema and the booking guard use only portable features, and the PostgreSQL driver is installed, but the first PostgreSQL deployment should be treated as untested.
- **Location data is an older PSGC snapshot** (17 regions, 81 provinces). See `api/app/data/psgc/SOURCE.md`.
- **Email addresses are not verified** and there is no password reset. Both need an email provider.
- **Access tokens are kept in `localStorage`.** That is simple and works across the separate web and API hosts, but any script injected into the page could read the token. Moving the API behind the web origin and using an HttpOnly cookie is the stronger setup.
- **Rate limiting is per process** and keyed on the connecting address. Behind a proxy the API needs forwarded headers enabled to see real client addresses, and more than one instance needs a shared store.
- **No online payments.** Reservations record "pay at venue".
- **Queue screens poll** every eight seconds rather than receiving pushed updates.
- **Tournament brackets are not built.** `tournament` and `event` are session kinds with registration and capacity only.
- **The host form assumes Philippine time (UTC+8)** when turning the chosen date and time into a timestamp.
- **Session fees are informational.** They are paid to the host in person.
- **Opening hours cannot cross midnight**, and each weekday has a single opening period.
- **Bookings use 15-minute steps**, so tee times at 10-minute intervals are not representable.
- **SQLite serialises all database access.** Fine for development and the demo; production traffic should use PostgreSQL.
- **OpenStreetMap's public tile server** is used for maps. It is meant for light use; set `VITE_MAP_TILE_URL` to a tile provider for production.
- **Distance search computes distances in the application** after a bounding-box filter. That is fine for thousands of venues; a spatial index is the next step beyond that.
