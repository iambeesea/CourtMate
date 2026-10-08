# Implementation status

Branch `feat/courtmate-multisport`. Updated at the end of each phase. Design is in `ARCHITECTURE.md`; the starting point is in `AUDIT.md`.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | GitHub connection, audit, architecture | Done |
| 2 | Universal sports foundation | Done |
| 3 | Open plays | Done |
| 4 | Communities and statistics | Done |
| 5 | Facility management | Done |
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

## Phase 4 — Communities and statistics

**API**

- Communities with members, roles, sports and a home city; public or private; filters by sport, location and text. Sessions can be hosted for a community and listed by it.
- Teams per sport, optionally inside a community, with a captain and roster. A player joining a session can tag one of their own teams.
- Player records per sport, computed on request and never stored:
  - head-to-head sports from completed matches: played, won, lost, drawn where the sport allows it, win rate, current and best streak, games or sets won, team totals, per-player lines (points, rebounds, assists, goals…) only where someone recorded them, and most frequent partners;
  - individual sports from logged activities, using the aggregations in the sport's configuration (total distance, average pace, average speed, personal best, best round…);
  - class and meet-up sports from checked-in attendance at finished sessions.
- A sport with nothing recorded returns `hasData: false` and no figures.
- Self-reported activity logging, validated against the sport's fields, and match history.
- Achievements derived from records (first result, winning streak, regular, multi-sport, community member, host).
- In-app notifications with an unread count: waitlist promotion, join requests and decisions, removal, reschedules and cancellations.
- Demo communities (the original three plus two more), teams and sample results for the demo player. All flagged as demo.

**Web**

- Communities tab with discovery, "mine", creation, community pages (sessions, teams, members) and team pages.
- Profile now holds the player record: one tab per sport, a headline figure, recent form, a stat grid that adapts to the sport, activity by month, partners, match or activity history, and achievements.
- Logging form generated from the sport's activity fields.
- The Instagram Story card works for any sport's record and marks demo figures as demo.
- Notification bell with unread count and a notifications page.
- The original MVP screens and their bundled demo figures are gone.

## Phase 5 — Facility management

**API** (`/api/v1/operator/*`, staff of the facility only; everyone else receives 404)

- Register a facility. It starts `pending`: private, unlisted and unbookable until an administrator verifies it.
- Edit details, private contact information and booking rules; replace the weekly opening hours.
- Add and edit bookable spaces, set prices and booking lengths, take a space off sale, and divide a space into sections (half courts, pool lanes). A space with bookings held against it cannot be divided until they are finished.
- Day schedule for every space, including before verification.
- Block time for maintenance or private use; blocking fails if a booking is in the way.
- Reservation lists (requests, upcoming, history, blocks); accept or decline requests; cancel a booking from the venue side with a reason.
- Occupancy report per bookable unit over a date range: open, booked and blocked time, booking counts, and booked value at listed rates.
- Notifications both ways: the venue hears about new requests and customer cancellations; the customer hears about confirmations, declines and venue cancellations.

**Administration** (`/api/v1/admin/facilities`): review queue by status with the operator's contact details, and verify, reject or suspend. The owner is notified.

**Web**

- Venue dashboard at `/operator`: registration form, and per venue an overview, bookings, schedule, spaces, hours and rules, and details.
- Verification screen at `/admin` for administrators.
- Links from Profile.

Operator contact details and verification notes are returned only by the operator and admin routes; a test asserts they are absent from the public facility responses.

## How to run

```bash
# Terminal 1
cd api && uv sync && uv run fastapi dev

# Terminal 2
cd web && npm install && npm run dev
```

Open <http://localhost:5173>. "Sign in → Demo player" needs no password.

## Checks

| Check | Command | Latest result (end of phase 5) |
| --- | --- | --- |
| API tests | `cd api && uv run pytest` | 154 passed |
| API lint and format | `uv run ruff check . && uv run ruff format --check .` | Clean |
| Web type check and build | `cd web && npm run build` | Clean |
| Web lint | `npm run lint` | Clean |
| Web unit tests | `npm test` | 9 passed (also with `TZ=America/New_York`) |
| Browser walk-through | Explore → venue → pick slots → demo sign-in → confirm → Bookings; location filter on a phone-sized viewport; session page → check in to the live queue; host form for running and badminton; player record, share card and Communities; venue dashboard → accept a booking request | Worked |

## Known limitations

- **PostgreSQL has not been exercised.** Every test and manual check ran on SQLite. The schema and the booking guard use only portable features, and the PostgreSQL driver is installed, but the first PostgreSQL deployment should be treated as untested.
- **Location data is an older PSGC snapshot** (17 regions, 81 provinces). See `api/app/data/psgc/SOURCE.md`.
- **Email addresses are not verified** and there is no password reset. Both need an email provider.
- **Access tokens are kept in `localStorage`.** That is simple and works across the separate web and API hosts, but any script injected into the page could read the token. Moving the API behind the web origin and using an HttpOnly cookie is the stronger setup.
- **Rate limiting is per process** and keyed on the connecting address. Behind a proxy the API needs forwarded headers enabled to see real client addresses, and more than one instance needs a shared store.
- **No online payments.** Reservations record "pay at venue". The dashboard's "booked value" is bookings at listed rates, not money received.
- **Facility verification is a manual decision** by an administrator. There is no document upload, and the first administrator account has to be created outside the app (see Deployment).
- **One operator account per facility in the web UI.** The schema has staff roles (owner, manager), but there is no screen for inviting staff.
- **Venue photos** can be stored as HTTPS links through the API; there is no upload.
- **Results are trusted as entered.** A match score is recorded by the host or one of its players, and activities are self-reported; there is no second confirmation or dispute step.
- **Notifications are in-app only** and the badge refreshes once a minute. There is no push or email.
- **Private communities have no invitation flow yet**; the API supports them, the web only creates public ones.
- **Queue screens poll** every eight seconds rather than receiving pushed updates.
- **Tournament brackets are not built.** `tournament` and `event` are session kinds with registration and capacity only.
- **The host form assumes Philippine time (UTC+8)** when turning the chosen date and time into a timestamp.
- **Session fees are informational.** They are paid to the host in person.
- **Opening hours cannot cross midnight**, and each weekday has a single opening period.
- **Bookings use 15-minute steps**, so tee times at 10-minute intervals are not representable.
- **SQLite serialises all database access.** Fine for development and the demo; production traffic should use PostgreSQL.
- **OpenStreetMap's public tile server** is used for maps. It is meant for light use; set `VITE_MAP_TILE_URL` to a tile provider for production.
- **Distance search computes distances in the application** after a bounding-box filter. That is fine for thousands of venues; a spatial index is the next step beyond that.
