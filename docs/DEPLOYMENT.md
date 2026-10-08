# Deployment

CourtMate deploys as two pieces: the web app (static files, Vercel) and the API (Render). Deploy them together; the web app on this branch does not work against the API on `main` at `44f2380`, and the reverse.

## API (Render)

`render.yaml` describes the service. On start the API applies database migrations, loads the sport catalog and Philippine location data, and (if enabled) loads demo data.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | SQLite file | PostgreSQL URL. `postgres://` and `postgresql://` are both accepted. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated web origins allowed to call the API. Set this to the Vercel URL(s). |
| `ENVIRONMENT` | `development` | `production` adds `Strict-Transport-Security` and turns the demo administrator off by default. |
| `SEED_DEMO_DATA` | `true` | Load labelled demo venues, sessions, communities and results. |
| `DEMO_LOGIN` | follows `SEED_DEMO_DATA` | Password-less sign-in as the demo player or demo venue operator. |
| `DEMO_ADMIN_LOGIN` | on in development, off in production | Password-less sign-in as the demo administrator. |
| `AUTO_MIGRATE` | `true` | Apply migrations on start. |
| `TOKEN_TTL_HOURS` | `336` | How long a sign-in lasts. |
| `RATE_LIMIT_ENABLED` | `true` | Limit sign-in and registration attempts per address. |
| `MAX_BODY_BYTES` | `262144` | Largest request body accepted. |
| `FORWARDED_ALLOW_IPS` | unset | Set to `*` behind Render's proxy so rate limiting sees real client addresses. |

### Database

- **Without `DATABASE_URL`** the API writes a SQLite file next to the code. On Render that file is recreated on every deploy and restart, so accounts and bookings do not survive. That is acceptable for a demo and nothing else.
- **For anything real, set `DATABASE_URL` to PostgreSQL.** The schema and the booking guard use only portable SQL, and the PostgreSQL driver is installed, but this branch was tested on SQLite only. Run the first PostgreSQL deployment as a rehearsal: start the service, register an account, make a booking, join a session.
- Demo data and real data can share a database (demo rows are flagged), but a real launch should start from an empty database with `SEED_DEMO_DATA=false`.

### The first administrator

Administrators edit the sport catalog and verify venues. Nobody can become one through the app. After the person has registered:

```bash
cd api
python -m app.manage make-admin someone@example.com
```

On Render, run this from the service's shell.

## Web (Vercel)

- Root directory `web`, build command `npm run build`, output `dist`.
- `VITE_API_URL` (in `web/.env.production`, or a Vercel environment variable) points at the API.
- `web/vercel.json` rewrites every path to the single-page app and sets the security headers, including the Content-Security-Policy. If map tiles or fonts move to another host, that policy is where to allow them.
- `VITE_MAP_TILE_URL` and `VITE_MAP_ATTRIBUTION` switch the map to a tile provider. OpenStreetMap's public tile server, the default, is for light use only.

Pull-request previews on Vercel are built with the production `VITE_API_URL`. Until the API from this branch is deployed there, a preview will load but show "Can't reach CourtMate" style errors for the new screens.

## Going live checklist

1. PostgreSQL provisioned and `DATABASE_URL` set.
2. `SEED_DEMO_DATA=false` and `DEMO_LOGIN=false`.
3. `CORS_ORIGINS` lists exactly the production web origin(s).
4. `ENVIRONMENT=production` and `FORWARDED_ALLOW_IPS=*`.
5. First administrator created with `app.manage`.
6. A map tile provider configured.
7. Location data refreshed if a newer PSGC release matters to you (`api/app/data/psgc/SOURCE.md`).
8. Read "Known limitations" in `IMPLEMENTATION.md`: no email verification or password reset, no online payments, tokens in `localStorage`, single-process rate limiting.

## What is not set up

- **Payments.** Reservations and session fees are settled in person. `payment_status` exists so a provider can be added.
- **Email or SMS.** Needed for verification, password reset and off-app notifications.
- **Native apps.** The web app is installable; store packaging is a later step.
- **Backups, monitoring and error reporting** for the API.
