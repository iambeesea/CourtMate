"""Passwords, access tokens, permission dependencies and a small rate limiter."""

import base64
import datetime as dt
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuthToken, Facility, FacilityStaff, User, utcnow

_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=256 * n * r)


def hash_password(password: str) -> str:
    n = get_settings().scrypt_n
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, n, _SCRYPT_R, _SCRYPT_P)
    return "$".join(["scrypt", str(n), str(_SCRYPT_R), str(_SCRYPT_P), base64.b64encode(salt).decode(), base64.b64encode(digest).decode()])


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check so unknown emails are not distinguishable by timing."""
    _scrypt(password, b"courtmate-unknown", get_settings().scrypt_n, _SCRYPT_R, _SCRYPT_P)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(db: Session, user: User) -> tuple[str, dt.datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + dt.timedelta(hours=get_settings().token_ttl_hours)
    db.add(AuthToken(user_id=user.id, token_hash=_digest(token), expires_at=expires_at))
    return token, expires_at


def revoke_token(db: Session, token: str) -> None:
    record = db.scalar(select(AuthToken).where(AuthToken.token_hash == _digest(token)))
    if record and record.revoked_at is None:
        record.revoked_at = utcnow()


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _user_for(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    record = db.scalar(select(AuthToken).where(AuthToken.token_hash == _digest(token)))
    if record is None or record.revoked_at is not None or record.expires_at <= utcnow():
        return None
    user = db.get(User, record.user_id)
    return user if user and user.is_active else None


def optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User | None:
    return _user_for(db, _bearer(authorization))


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    user = _user_for(db, _bearer(authorization))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return user


def current_token(authorization: str | None = Header(default=None)) -> str | None:
    return _bearer(authorization)


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access is required.")
    return user


def staff_role(db: Session, facility_id: str, user: User) -> str | None:
    """The user's role at a facility, or None. Administrators act as owners."""
    if user.role == "admin":
        return "owner"
    return db.scalar(select(FacilityStaff.role).where(FacilityStaff.facility_id == facility_id, FacilityStaff.user_id == user.id))


def require_facility_staff(db: Session, facility_id: str, user: User, *, owner_only: bool = False) -> Facility:
    facility = db.get(Facility, facility_id)
    role = staff_role(db, facility_id, user) if facility else None
    # Answer 404 rather than 403 so facility ids cannot be probed.
    if facility is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facility not found.")
    if owner_only and role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the facility owner can do this.")
    return facility


class RateLimiter:
    """Sliding-window limiter held in process memory.

    Good enough to slow password guessing on a single instance. A shared store
    is needed once the API runs on more than one process.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        if not get_settings().rate_limit_enabled:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many attempts. Please wait and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def client_key(request: Request, scope: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{scope}:{host}"
