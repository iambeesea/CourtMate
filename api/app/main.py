import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import schemas, seed
from .config import get_settings
from .db import configure, session_factory
from .migrate import run_migrations
from .routers import admin, auth, communities, facilities, geo, players, reservations, sessions, sports
from .timeutil import DEFAULT_TIMEZONE, QUANTUM_MINUTES

VERSION = "0.2.0"
logger = logging.getLogger("courtmate")


def bootstrap() -> None:
    """Prepare the database: apply migrations, then load reference and (optionally) demo data."""
    settings = get_settings()
    configure(settings.database_url)
    if settings.auto_migrate:
        run_migrations()
    with session_factory()() as db:
        seed.seed_reference(db)
        if settings.seed_demo_data and seed.seed_demo(db):
            logger.info("Loaded demonstration data")


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap()
    yield


app = FastAPI(
    title="CourtMate API",
    description="Multi-sport discovery, facility booking, open play, communities and player records for the Philippines.",
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    # Access tokens travel in the Authorization header, so cross-site cookies are never needed.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Responses can carry account data; only routes that opt in (reference data) are cacheable.
    response.headers.setdefault("Cache-Control", "no-store")
    if get_settings().environment == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


for module in (auth, sports, geo, facilities, reservations, sessions, players, communities, admin):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/", tags=["system"])
def root():
    return {"name": "CourtMate API", "version": VERSION, "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/api/v1/config", response_model=schemas.AppConfig, tags=["system"])
def read_config():
    settings = get_settings()
    return schemas.AppConfig(
        demo_login=settings.demo_login,
        demo_data=settings.seed_demo_data,
        default_timezone=DEFAULT_TIMEZONE,
        booking_quantum_minutes=QUANTUM_MINUTES,
        version=VERSION,
    )
