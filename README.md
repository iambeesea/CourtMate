# CourtMate

CourtMate is a mobile-first community platform for discovering and joining pickleball and badminton open-play sessions. The MVP includes live queue changes, player records, local communities, and Instagram Story-ready match cards.

## Instagram Story sharing

The player record screen renders a 1080 × 1920 PNG match recap in the browser. On supported mobile devices, **Share to Instagram Story** opens the operating system's native share sheet with the generated image attached; the player can choose Instagram and then Stories. If file sharing is unavailable, CourtMate downloads the PNG so it can be uploaded manually.

This mirrors the user-facing flow of native sports apps while staying within browser capabilities. A future Capacitor or React Native shell can replace the Web Share call with Android implicit intents and Instagram's iOS `instagram-stories://share` integration for direct handoff to the Story composer.

## Brand palette

- White: `#FFFFFF`
- Light gray: `#E8E8E8`
- Court navy: `#1F3B73`
- Rally lime: `#E0FE2C`

## Stack

- React 19 + TypeScript + Vite
- FastAPI + Pydantic + uv
- Vercel-ready web deployment
- FastAPI Cloud and Render-ready API deployment

## Local development

```bash
# Terminal 1
cd api
uv run fastapi dev

# Terminal 2
cd web
npm install
npm run dev
```

The web app runs at `http://localhost:5173` and calls the API at `http://localhost:8000` by default.

## API

- `GET /health`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions/{id}/join`
- `POST /api/v1/sessions/{id}/leave`
- `GET /api/v1/players/me/stats`
- `GET /api/v1/communities`

The current MVP uses seeded in-memory data. Replace `api/app/store.py` with a repository backed by PostgreSQL before production traffic.
