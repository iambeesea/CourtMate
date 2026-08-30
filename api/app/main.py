import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import communities, players, sessions

app = FastAPI(title="CourtMate API", description="Open-play discovery, player queues, communities, and performance records.", version="0.1.0")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(players.router, prefix="/api/v1")
app.include_router(communities.router, prefix="/api/v1")


@app.get("/", tags=["system"])
def root():
    return {"name": "CourtMate API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
