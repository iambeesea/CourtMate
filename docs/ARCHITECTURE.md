# CourtMate multi-sport architecture

CourtMate is one system that serves many sports. Nothing in the core is written for a particular sport: sports, resource types and location data are rows, and sport-specific behaviour is driven by configuration stored on the sport.

```
web/  React 19 SPA (Vite, React Router)  ──HTTPS/JSON──▶  api/  FastAPI
                                                            │
                                                            ▼
                                             SQLAlchemy 2 ─ SQLite (dev/demo) or PostgreSQL (production)
```

## 1. Sport catalog as data

A sport is a row in `sports`. Administrators add or edit sports through `POST/PATCH /api/v1/admin/sports`; no deploy is needed.

| Column | Purpose |
| --- | --- |
| `id`, `name`, `category_id`, `icon` | Identity. `icon` is an emoji or a `cm:` key for a bundled glyph. |
| `booking_eligible` | Whether the sport books facility resources. |
| `queue_eligible` | Whether live sessions can run a player queue. |
| `player_config` | `minPlayers`, `maxPlayers`, `teamFormats[]` (id, label, players per side). |
| `match_format` | `type` (`two_sided`, `individual`, `class`, `group`), `sessionKinds[]`, `queueModes[]`, `skillLevels[]`, `usesRoutes`. |
| `scoring_config` | `kind` (`games`, `total`, `result`, `individual`, `none`), `unit`, `bestOf`, `allowDraw`, `playerFields[]`, `activityFields[]`, `aggregations[]`. |
| `resource_types` | Which resource types the sport can be played on. |

The web reads this configuration to decide which controls to show, so a running group never sees court queues and a bowling booking never asks for a team format.

Thirty sports across six categories are seeded from `app/sports_catalog.py`. That file is data only.

## 2. Facilities and bookable resources

```
facilities ─┬─ facility_hours        (weekday, open minute, close minute)
            ├─ facility_sports       (which sports the venue supports)
            ├─ facility_staff        (operator accounts and their role)
            └─ resources ─┬─ resource_sports
                          └─ resources (children, e.g. half courts)
```

- `resources.resource_type_id` references `resource_types` (court, half court, field, lane, table, studio, pool, pool lane, training area, tee, ring, climbing wall, track, other). The list is a table, not an enum.
- A resource may have one level of children. A full basketball court with two half-court children is three rows.
- Facilities carry a `verification_status` (`pending`, `verified`, `rejected`, `suspended`) and an `is_demo` flag. Only verified or demo facilities are publicly listed and bookable. Demo records are labelled as such everywhere they appear.
- Operator contact details and verification notes live on the facility but are only serialised by the operator and admin schemas.

## 3. Booking engine and double-booking prevention

Reservations occupy time in 15-minute quanta. Each active reservation owns one row per quantum per *unit resource* in `reservation_slots`, whose primary key is `(unit_resource_id, slot_start)`.

- A leaf resource is its own unit.
- A parent resource's units are its children. Booking the full court writes slot rows for both halves; booking one half writes rows for that half only. Full/half conflicts therefore fall out of the same key.

Creating a reservation inserts the reservation and its slot rows in one transaction. If any slot is already taken the database rejects the insert, the transaction rolls back, and the API answers `409`. Correctness does not depend on application-level checks, isolation levels or locks, and the mechanism is identical on SQLite and PostgreSQL.

Cancelling or rejecting a reservation deletes its slot rows, which frees the time. Operator blocks ("court closed for maintenance") are reservations of kind `block` and use the same table. Weekly recurring reservations are created all-or-nothing in one transaction.

Booking rules are per facility: approval required, minimum notice, maximum advance window, minimum and maximum duration, free-cancellation window. The cancellation deadline is copied onto each reservation at booking time so a later rule change does not alter existing bookings.

Online payment is deliberately absent. Reservations carry a `payment_status` (`not_required`, `pay_at_venue`, `paid`, `refunded`) so a payment provider can be added without a schema change.

## 4. Open-play sessions

`play_sessions` covers open play, pickup games, classes, group runs and rides, tee times and events. A session has a sport, an optional facility (route-based activities use a meet-up point instead), capacity, minimum players, skill level, eligibility, fee, join policy and queue mode.

- **Capacity** is enforced with an atomic conditional update (`confirmed_count = confirmed_count + 1 WHERE confirmed_count < capacity`) backed by a `CHECK` constraint. Losing the race puts the player on the waitlist.
- **Waitlist** order is by join time. When a confirmed player leaves, the first waitlisted player is promoted and notified.
- **Approval** sessions hold joiners as `pending` until the host decides.
- **Queues** exist only for sports with `queue_eligible`. Checked-in players wait in order; the host calls the next match onto a free court; finishing a match re-queues the players (`rotation`) or keeps the winners on court (`winner_stays`).
- A session can hold a resource reservation, created in the same transaction as the session.

## 5. Time

All timestamps are stored in UTC. Every facility has an IANA time zone (default `Asia/Manila`). Opening hours are wall-clock minutes in the facility's zone and are converted through `zoneinfo` when availability is computed. The API emits ISO 8601 UTC; the web renders in `Asia/Manila` regardless of the device's zone.

## 6. Location

`geo_regions`, `geo_provinces`, `geo_cities` and `geo_barangays` are loaded from the Philippine Standard Geographic Code (see `api/app/data/psgc/SOURCE.md`). Facilities and sessions reference these codes, so filters by region, province, city/municipality and barangay are joins, not string matching. Cities in the National Capital Region and other independent cities have no province; the model allows that.

"Nearby" filtering uses facility or meet-up coordinates with a bounding-box pre-filter and a haversine distance. Nothing in the schema limits the application to particular regions.

## 7. Players, matches and statistics

One account has many sport profiles (`user_sports`). Results are recorded as:

- `matches` + `match_players` for two-sided play, with a score validated against the sport's `scoring_config`;
- `activity_logs` for individual activities (a run, a ride, a bowling game), with metrics validated against the sport's `activityFields`.

Statistics are computed on request from those rows using the sport's `aggregations`. When a player has no recorded results for a sport the API says so (`hasData: false`); it never fills in numbers.

## 8. Accounts and permissions

- Email + password accounts. Passwords are hashed with scrypt. Sign-in issues an opaque random token; only its SHA-256 digest is stored, and it can be revoked.
- Roles: `player` (default) and `admin`. Facility permissions are per facility through `facility_staff` (`owner`, `manager`). Session controls belong to the session host.
- Demo sign-in (`POST /api/v1/auth/demo`) exists only when `DEMO_LOGIN=true` and never accepts a password.

## 9. API surface

All routes are under `/api/v1`. The interactive reference is served at `/docs`.

| Area | Routes |
| --- | --- |
| Accounts | `auth/register`, `auth/login`, `auth/logout`, `auth/me`, `auth/demo` |
| Catalog | `sports`, `sports/categories`, `resource-types` |
| Location | `geo/regions`, `geo/provinces`, `geo/cities`, `geo/barangays` |
| Facilities | `facilities`, `facilities/{id}`, `facilities/{id}/availability`, `resources/{id}/availability` |
| Reservations | `reservations`, `reservations/{id}`, `reservations/{id}/cancel` |
| Sessions | `sessions`, `sessions/{id}`, `join`, `leave`, participants, queue, matches |
| Community | `communities`, `teams` |
| Players | `players/me/stats`, `players/me/activities`, `notifications` |
| Operators | `operator/facilities`, resources, hours, blocks, reservation decisions, occupancy |
| Admin | `admin/sports`, `admin/facilities/{id}/verification` |
