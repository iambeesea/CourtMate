from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..config import get_settings
from ..db import get_db
from ..models import GeoCity, Sport, User, UserSport
from ..security import (
    burn_password_check,
    client_key,
    current_token,
    current_user,
    hash_password,
    issue_token,
    rate_limiter,
    revoke_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["accounts"])

DEMO_EMAILS = {"player": "demo.player@courtmate.demo", "operator": "demo.operator@courtmate.demo", "admin": "demo.admin@courtmate.demo"}
AVATAR_COLORS = ["#1f3b73", "#2e90fa", "#12b76a", "#f79009", "#7f56d9", "#ee46bc", "#15b79e", "#f63d68"]


def _token_response(db: Session, user: User) -> schemas.TokenOut:
    token, expires_at = issue_token(db, user)
    db.commit()
    return schemas.TokenOut(access_token=token, expires_at=expires_at, user=serializers.me(db, user))


@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check(client_key(request, "register"), limit=10, window_seconds=3600)
    email = payload.email.strip().lower()
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        avatar_color=AVATAR_COLORS[sum(email.encode()) % len(AVATAR_COLORS)],
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.") from None
    return _token_response(db, user)


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check(client_key(request, "login"), limit=10, window_seconds=300)
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not user.password_hash:
        burn_password_check(payload.password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return _token_response(db, user)


@router.post("/demo", response_model=schemas.TokenOut)
def demo_login(payload: schemas.DemoLoginIn, request: Request, db: Session = Depends(get_db)):
    """Sign in as a seeded demo persona. Only exists when DEMO_LOGIN is on; demo accounts have no password."""
    settings = get_settings()
    if not settings.demo_login or (payload.persona == "admin" and not settings.demo_admin_login):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo sign-in is not enabled.")
    rate_limiter.check(client_key(request, "demo"), limit=30, window_seconds=300)
    user = db.scalar(select(User).where(User.email == DEMO_EMAILS[payload.persona], User.is_demo.is_(True)))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo data has not been loaded.")
    return _token_response(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str | None = Depends(current_token), db: Session = Depends(get_db)):
    if token:
        revoke_token(db, token)
        db.commit()


@router.get("/me", response_model=schemas.Me)
def read_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serializers.me(db, user)


@router.patch("/me", response_model=schemas.Me)
def update_me(payload: schemas.ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, user.id)
    fields = payload.model_fields_set
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.bio is not None:
        user.bio = payload.bio.strip()
    if "city_code" in fields:
        if payload.city_code and db.get(GeoCity, payload.city_code) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown city or municipality code.")
        user.city_code = payload.city_code or None
    if payload.sports is not None:
        wanted = {item.sport_id: item for item in payload.sports}
        known = set(db.scalars(select(Sport.id).where(Sport.id.in_(wanted))).all())
        if unknown := sorted(set(wanted) - known):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown sport: {', '.join(unknown)}.")
        user.sports = [
            UserSport(user_id=user.id, sport_id=sport_id, skill_level=item.skill_level.strip(), is_primary=item.is_primary)
            for sport_id, item in wanted.items()
        ]
    db.commit()
    db.refresh(user)
    return serializers.me(db, user)
