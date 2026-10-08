# Changelog

All notable changes to CourtMate are recorded here. Dates are in Philippine time.

## [Unreleased] — `feat/courtmate-multisport`

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
