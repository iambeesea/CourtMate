# Baseline audit — CourtMate MVP

Audit of the project as it stood on `main` at commit `44f2380` ("Connect production web app to Render API"), which is byte-identical to the ZIP supplied for this work.

## Repository state

| Item | Finding |
| --- | --- |
| Remote | `github.com/iambeesea/CourtMate` (public), default branch `main` |
| History | 4 commits, single branch, no pull requests, no issues |
| ZIP vs. remote | Identical to `origin/main` — no baseline commit was required |
| CI | None |
| Tests | None (API or web) |

## What existed

**Web** (`web/`, React 19 + TypeScript + Vite 8)

- One 885-line `App.tsx` and one 1,522-line `App.css`; no router, no shared state layer.
- Four tabs: Discover, My sessions, Player record, Profile.
- Working: session list with a Pickleball/Badminton filter, join/leave with waitlist counting, a canvas-rendered 1080 × 1920 match card shared through the Web Share API (PNG download fallback).

**API** (`api/`, FastAPI)

- Six routes backed by module-level Python lists (`app/store.py`). Data resets on every restart.
- No database, authentication, permissions, validation beyond Pydantic shapes, or tests.

**Deployment**

- `render.yaml` for the API (free plan, Singapore), `vercel.json` SPA rewrite for the web.
- `web/.env.production` points at `https://courtmate-api-live.onrender.com`.

## Defects found in the baseline

| # | Area | Defect |
| --- | --- | --- |
| 1 | API | Join/leave mutates one shared `is_joined` flag, so every visitor shares a single "joined" state. |
| 2 | API | Leaving a full session with a waitlist decrements the waitlist instead of freeing a spot and promoting the next player. |
| 3 | API | No guard against concurrent joins exceeding capacity. |
| 4 | Web | `api.ts` swallows every network error and silently substitutes demo data; join/leave then "succeeds" locally with the API down. |
| 5 | Web | Hard-coded dates and copy: "SATURDAY, AUGUST 29", month label "SEP", "13 of 16 players", "3 spots left". |
| 6 | Web | "My sessions" shows the first session as joined when the player has joined nothing. |
| 7 | Web | Statistics (rating 3.12, "+0.18 this month", monthly chart, badges, 4-week streak) are constants, not derived from any match data. |
| 8 | Web | "Host a session", "Create session", search, location, Level and Distance controls are inert. |
| 9 | Web | Session dates parse as local time; a device outside Philippine time can show the wrong day. |
| 10 | Web | `theme-color` is `#242846`, not Court Navy `#1F3B73`. |
| 11 | Both | Sport is a closed `Pickleball | Badminton` union in both the API model and the web types. |

## What must be preserved

- Session discovery, join, leave and waitlist behaviour.
- The player record screen and the Instagram Story match card (canvas render, native share sheet, PNG fallback).
- Communities listing.
- The brand palette and the desktop sidebar / mobile bottom-nav layout.
- Vercel + Render deployment without mandatory new infrastructure.
- The existing route paths (`/health`, `/api/v1/sessions`, `/api/v1/sessions/{id}/join|leave`, `/api/v1/players/me/stats`, `/api/v1/communities`).

## Local environment notes

The development machine had Node 26 but only the system Python 3.9 and no `uv`, PostgreSQL or Docker. The API toolchain is therefore run through a project-local virtualenv (`api/.venv`, Python 3.12). All database behaviour in this branch was exercised against SQLite; PostgreSQL has not been exercised locally (see `docs/IMPLEMENTATION.md`, Known limitations).
