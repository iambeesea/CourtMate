# Changelog

All notable changes to CourtMate are recorded here. Dates are in Philippine time.

## [Unreleased] — `feat/courtmate-multisport`

### Phase 5 — Facility management (2026-10-08)

Added

- Facility operator API under `/api/v1/operator`: registration, details and booking rules, opening hours, bookable spaces and sections, day schedule, time blocks, reservation lists, accept/decline/cancel, and an occupancy report.
- Administrator verification: `/api/v1/admin/facilities` review queue and `/api/v1/admin/facilities/{id}/verification`.
- Notifications between venues and customers for requests, decisions and cancellations.
- Web: venue dashboard (`/operator`), venue verification (`/admin`), demo admin sign-in.
- 16 more API tests (154 in total).

Security

- Operator routes answer 404 to anyone who is not staff at that facility, so facility and reservation ids cannot be probed.
- Operator contact details and verification notes never appear in public responses (covered by tests).

### Phase 4 — Communities and statistics (2026-10-08)

Added

- Communities and teams: `/api/v1/communities`, `/api/v1/teams`, with membership, roles and discovery filters.
- Per-sport player records computed from recorded matches, logged activities and checked-in attendance: `/api/v1/players/me/records`, `stats`, `matches`, `activities`, `achievements`.
- In-app notifications: `/api/v1/notifications` and `/api/v1/notifications/read`.
- Web: Communities tab, community and team pages, the player record inside Profile, activity logging, notification bell and page.
- 25 more API tests (138 in total).

Changed

- Navigation is now Explore, Bookings, Play, Communities, Profile.
- `GET /api/v1/players/me/stats` and `GET /api/v1/communities` keep their paths but return records computed from data, and the stats route requires sign-in.
- The Instagram Story card is generated from the selected sport's record. Demo figures are labelled on the card.
- `/record` redirects to `/profile`.

Fixed

- Statistics are no longer constants. Rating, "+0.18 this month", the monthly chart, badges and the streak are either computed from recorded results or not shown (audit item 7).

Removed

- The remaining in-memory API data and the original single-file web screens.

### Phase 3 — Open plays (2026-10-08)

Added

- Database-backed sessions for every sport, with discovery filters and distance search.
- Hosting: one-off or weekly sessions at a listed venue or a described meet-up point, with an optional venue reservation made in the same step.
- Waitlists with automatic, ordered promotion and a notification to the promoted player.
- Approval-based sessions and host controls (approve, decline, remove, check in, edit, reschedule, start, finish, cancel).
- Live queues with `rotation` and `winner_stays` modes, court assignment, sport-specific score entry and match voiding.
- Web: session cards and filters on Explore, session page, host form, Play tab.
- 35 more API tests (113 in total).

Changed

- `GET /api/v1/sessions` and `POST /api/v1/sessions/{id}/join|leave` keep their paths but now return the multi-sport session shape, and join/leave require sign-in.

Fixed

- Joined state is per player instead of one flag shared by every visitor (audit item 1).
- Leaving a full session frees the place for the first waitlisted player instead of shrinking the waitlist (audit item 2).
- Concurrent joins can no longer exceed capacity (audit item 3).
- Join and leave no longer appear to succeed while the API is unreachable (audit item 4).
- "My sessions" no longer shows a session the player never joined, and the hard-coded "13 of 16 players" and "SEP" labels are gone (audit items 5 and 6).
- "Host a session" and "Create session" now do something (part of audit item 8).

Removed

- The seeded in-memory session list and the web's silent fallback to bundled demo sessions.

### Phase 2 — Universal sports foundation (2026-10-08)

Added

- Relational database (SQLAlchemy 2, Alembic) replacing the in-memory lists for everything new. SQLite locally, PostgreSQL via `DATABASE_URL`.
- Sport catalog with 30 sports in 6 categories, configured per sport, editable by administrators through `POST/PATCH /api/v1/admin/sports`.
- Philippine location data (PSGC) and `/api/v1/geo/*` routes.
- Accounts: `/api/v1/auth/register`, `login`, `logout`, `me`, plus password-less demo personas when `DEMO_LOGIN` is on.
- Facilities, bookable resources, opening hours and booking rules; `/api/v1/facilities` with sport, location, resource-type, text and distance filters.
- Day availability and `/api/v1/reservations` with double-booking prevention enforced by the database, full/half resource conflicts, weekly series and cancellation.
- Web: routing, sport picker, location picker, venue list and map, venue page with booking calendar, Bookings page, sign-in and profile editing.
- API tests (78) and web unit tests (9).

Changed

- Web navigation is now Explore, Bookings, Play, Profile.
- CORS no longer allows credentials; access tokens travel in the `Authorization` header.
- API responses carry `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Cache-Control: no-store` by default.
- `theme-color` is Court Navy `#1F3B73`.

Fixed

- Dates and times render in Philippine time regardless of the device time zone (audit item 9).
- The Explore header shows today's date instead of a fixed one (part of audit item 5).

### Phase 1 — GitHub and architecture (2026-10-08)

- Verified the supplied ZIP against `github.com/iambeesea/CourtMate`; it matches `main` at `44f2380`.
- Created the `feat/courtmate-multisport` branch.
- Added the baseline audit (`docs/AUDIT.md`) and the multi-sport architecture (`docs/ARCHITECTURE.md`).
- Added the Philippine Standard Geographic Code seed files and the script that builds them.

## [0.1.0] — 2026-08-31

- Initial MVP: pickleball and badminton open-play discovery, join/leave with waitlist, player record, Instagram Story match card, communities endpoint.
