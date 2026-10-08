import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import Match, PlaySession, SessionParticipant, Sport, User
from ..security import current_user, optional_user
from ..services import booking
from ..services import sessions as service
from ..services.geo import bounding_box, haversine_km
from ..timeutil import utcnow

router = APIRouter(tags=["sessions"])

MAX_RADIUS_KM = 300.0


def _fail(error: service.SessionError | booking.BookingError) -> HTTPException:
    return HTTPException(error.status_code, error.message)


def _session(db: Session, session_id: str) -> PlaySession:
    session = db.get(PlaySession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    return session


def _managed(db: Session, session_id: str, user: User) -> PlaySession:
    session = _session(db, session_id)
    if not service.can_manage(session, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host can do this.")
    return session


def _participant(db: Session, session: PlaySession, participant_id: str) -> SessionParticipant:
    participant = db.get(SessionParticipant, participant_id)
    if participant is None or participant.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found in this session.")
    return participant


def _own_participant(db: Session, session: PlaySession, user: User) -> SessionParticipant:
    participant = service.participant_for(db, session.id, user.id)
    if participant is None or participant.status not in service.ACTIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are not in this session.")
    return participant


def _detail(db: Session, session: PlaySession, viewer: User | None) -> schemas.SessionDetail:
    db.refresh(session)
    return serializers.session_detail(session, viewer)


# --- discovery ----------------------------------------------------------------


@router.get("/sessions", response_model=list[schemas.SessionOut])
def list_sessions(
    response: Response,
    sport_id: str | None = Query(default=None, alias="sportId"),
    category: str | None = Query(default=None, description="Sport category id"),
    kind: str | None = None,
    region_code: str | None = Query(default=None, alias="regionCode"),
    province_code: str | None = Query(default=None, alias="provinceCode"),
    city_code: str | None = Query(default=None, alias="cityCode"),
    barangay_code: str | None = Query(default=None, alias="barangayCode"),
    facility_id: str | None = Query(default=None, alias="facilityId"),
    community_id: str | None = Query(default=None, alias="communityId"),
    starts_after: dt.datetime | None = Query(default=None, alias="startsAfter"),
    starts_before: dt.datetime | None = Query(default=None, alias="startsBefore"),
    skill_level: str | None = Query(default=None, alias="skillLevel"),
    free: bool | None = Query(default=None, description="Only sessions with no fee"),
    has_spots: bool | None = Query(default=None, alias="hasSpots"),
    q: str | None = Query(default=None, min_length=2, max_length=80),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=15.0, gt=0, le=MAX_RADIUS_KM, alias="radiusKm"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    """Upcoming and live sessions, soonest first. Pass `lat` and `lng` to search by distance."""
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide both lat and lng, or neither.")
    for moment in (starts_after, starts_before):
        if moment is not None and moment.tzinfo is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Timestamps must include a UTC offset.")

    now = utcnow()
    query = select(PlaySession).where(PlaySession.status.in_(("scheduled", "live")), PlaySession.end_at > now)
    if sport_id:
        query = query.where(PlaySession.sport_id == sport_id)
    if category:
        query = query.where(PlaySession.sport_id.in_(select(Sport.id).where(Sport.category_id == category)))
    if kind:
        query = query.where(PlaySession.kind == kind)
    if region_code:
        query = query.where(PlaySession.region_code == region_code)
    if province_code:
        query = query.where(PlaySession.province_code == province_code)
    if city_code:
        query = query.where(PlaySession.city_code == city_code)
    if barangay_code:
        query = query.where(PlaySession.barangay_code == barangay_code)
    if facility_id:
        query = query.where(PlaySession.facility_id == facility_id)
    if community_id:
        query = query.where(PlaySession.community_id == community_id)
    if starts_after:
        query = query.where(PlaySession.start_at >= starts_after)
    if starts_before:
        query = query.where(PlaySession.start_at < starts_before)
    if skill_level:
        query = query.where(PlaySession.skill_level.in_((skill_level, "All levels")))
    if free:
        query = query.where(PlaySession.fee_centavos == 0)
    if has_spots:
        query = query.where(PlaySession.confirmed_count < PlaySession.capacity)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(PlaySession.title.ilike(pattern), PlaySession.venue_name.ilike(pattern)))

    if lat is not None and lng is not None:
        min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
        query = query.where(PlaySession.latitude.between(min_lat, max_lat), PlaySession.longitude.between(min_lng, max_lng))
        rows = [(haversine_km(lat, lng, item.latitude, item.longitude), item) for item in db.scalars(query).unique().all()]
        rows = sorted(((distance, item) for distance, item in rows if distance <= radius_km), key=lambda pair: (pair[1].start_at, pair[0]))
        response.headers["X-Total-Count"] = str(len(rows))
        return [serializers.session(item, viewer, distance) for distance, item in rows[offset : offset + limit]]

    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.scalars(query.order_by(PlaySession.start_at, PlaySession.id).limit(limit).offset(offset)).unique().all()
    return [serializers.session(item, viewer) for item in rows]


@router.get("/sessions/mine", response_model=list[schemas.SessionOut])
def list_my_sessions(
    role: Literal["playing", "hosting"] = "playing",
    scope: Literal["upcoming", "past"] = "upcoming",
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Sessions the signed-in player has joined (including waitlisted and pending) or hosts."""
    now = utcnow()
    query = select(PlaySession)
    if role == "hosting":
        query = query.where(PlaySession.host_user_id == user.id)
    else:
        query = query.where(
            PlaySession.id.in_(
                select(SessionParticipant.session_id).where(
                    SessionParticipant.user_id == user.id, SessionParticipant.status.in_(service.ACTIVE_STATUSES)
                )
            )
        )
    if scope == "upcoming":
        query = query.where(PlaySession.status.in_(("scheduled", "live")), PlaySession.end_at > now).order_by(PlaySession.start_at)
    else:
        query = query.where(or_(PlaySession.status.in_(("completed", "cancelled")), PlaySession.end_at <= now)).order_by(
            PlaySession.start_at.desc()
        )
    return [serializers.session(item, user) for item in db.scalars(query.limit(limit)).unique().all()]


@router.get("/sessions/{session_id}", response_model=schemas.SessionDetail)
def read_session(session_id: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return serializers.session_detail(_session(db, session_id), viewer)


# --- hosting ------------------------------------------------------------------


@router.post("/sessions", response_model=list[schemas.SessionOut], status_code=status.HTTP_201_CREATED)
def create_session(payload: schemas.SessionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Host a session. Returns one session, or every occurrence of a weekly series."""
    try:
        sessions = service.create(db, user, payload)
        db.commit()
    except (service.SessionError, booking.BookingError) as error:
        db.rollback()
        raise _fail(error) from error
    for item in sessions:
        db.refresh(item)
    return [serializers.session(item, user) for item in sessions]


@router.patch("/sessions/{session_id}", response_model=schemas.SessionDetail)
def update_session(session_id: str, payload: schemas.SessionPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = _managed(db, session_id, user)
    try:
        service.update_session(db, session, payload)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _detail(db, session, user)


def _transition(db: Session, session_id: str, user: User, action: str, reason: str = "") -> schemas.SessionDetail:
    session = _managed(db, session_id, user)
    try:
        if action == "start":
            service.start_session(db, session)
        elif action == "complete":
            service.complete_session(db, session)
        else:
            service.cancel_session(db, session, user, reason)
        db.commit()
    except (service.SessionError, booking.BookingError) as error:
        db.rollback()
        raise _fail(error) from error
    return _detail(db, session, user)


@router.post("/sessions/{session_id}/start", response_model=schemas.SessionDetail)
def start_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Open check-in and the queue. Allowed from two hours before the start time."""
    return _transition(db, session_id, user, "start")


@router.post("/sessions/{session_id}/complete", response_model=schemas.SessionDetail)
def complete_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _transition(db, session_id, user, "complete")


@router.post("/sessions/{session_id}/cancel", response_model=schemas.SessionDetail)
def cancel_session(
    session_id: str, payload: schemas.CancelIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Cancel the session, tell everyone in it, and release any venue booking it holds."""
    return _transition(db, session_id, user, "cancel", (payload.reason if payload else "").strip())


@router.post("/sessions/{session_id}/participants/{participant_id}/{action}", response_model=schemas.SessionDetail)
def manage_participant(
    session_id: str,
    participant_id: str,
    action: Literal["approve", "decline", "remove", "check-in"],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = _managed(db, session_id, user)
    participant = _participant(db, session, participant_id)
    try:
        if action == "approve":
            service.decide(db, session, participant, approve=True)
        elif action == "decline":
            service.decide(db, session, participant, approve=False)
        elif action == "remove":
            service.remove(db, session, participant)
        else:
            service.check_in(db, session, participant)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _detail(db, session, user)


# --- playing ------------------------------------------------------------------


@router.post("/sessions/{session_id}/join", response_model=schemas.SessionDetail)
def join_session(session_id: str, payload: schemas.JoinIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Join a session. Full sessions put the player on the waitlist; approval sessions hold them as pending."""
    session = _session(db, session_id)
    try:
        service.join(db, session, user, team_id=payload.team_id if payload else None)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _detail(db, session, user)


@router.post("/sessions/{session_id}/leave", response_model=schemas.SessionDetail)
def leave_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Leave a session. A confirmed place passes to the first player on the waitlist."""
    session = _session(db, session_id)
    try:
        service.leave(db, session, user)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _detail(db, session, user)


@router.post("/sessions/{session_id}/check-in", response_model=schemas.QueueOut)
def check_in(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = _session(db, session_id)
    try:
        service.check_in(db, session, _own_participant(db, session, user))
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _queue(db, session, user)


# --- queue and matches --------------------------------------------------------


def _queue(db: Session, session: PlaySession, viewer: User | None) -> schemas.QueueOut:
    db.refresh(session)
    return serializers.queue(session, service.live_matches(db, session.id), viewer)


@router.get("/sessions/{session_id}/queue", response_model=schemas.QueueOut)
def read_queue(session_id: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    session = _session(db, session_id)
    return serializers.queue(session, service.live_matches(db, session.id), viewer)


@router.post("/sessions/{session_id}/queue/me", response_model=schemas.QueueOut)
def set_my_queue_state(session_id: str, payload: schemas.QueueStateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Step out of the queue for a rest (`idle`) or rejoin at the back (`waiting`)."""
    session = _session(db, session_id)
    try:
        service.set_queue_state(db, session, _own_participant(db, session, user), payload.state)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _queue(db, session, user)


@router.post("/sessions/{session_id}/queue/next", response_model=schemas.QueueOut)
def call_next_match(
    session_id: str, payload: schemas.NextMatchIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Send the players at the head of the queue to a free court."""
    session = _managed(db, session_id, user)
    try:
        service.call_next(db, session, user, court=payload.court if payload else None)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    return _queue(db, session, user)


@router.get("/sessions/{session_id}/matches", response_model=list[schemas.MatchOut])
def list_session_matches(session_id: str, db: Session = Depends(get_db)):
    session = _session(db, session_id)
    matches = db.scalars(
        select(Match).where(Match.session_id == session.id, Match.status != "void").order_by(Match.started_at.desc())
    ).all()
    return [serializers.match(item) for item in matches]


def _match_for_scoring(db: Session, match_id: str, user: User, *, host_only: bool) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found.")
    session = db.get(PlaySession, match.session_id) if match.session_id else None
    manages = session is not None and service.can_manage(session, user)
    played = user.id in {player.user_id for player in match.players}
    if not manages and (host_only or not played):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host or a player in this match can record its result.")
    return match


@router.post("/matches/{match_id}/result", response_model=schemas.MatchOut)
def record_match_result(match_id: str, payload: schemas.MatchResultIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Record the score. The shape must match the sport's scoring kind; players go back into the queue."""
    match = _match_for_scoring(db, match_id, user, host_only=False)
    try:
        service.record_result(db, match, payload, user)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    db.refresh(match)
    return serializers.match(match)


@router.post("/matches/{match_id}/void", response_model=schemas.MatchOut)
def void_match(match_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    match = _match_for_scoring(db, match_id, user, host_only=True)
    try:
        service.void_match(db, match)
        db.commit()
    except service.SessionError as error:
        db.rollback()
        raise _fail(error) from error
    db.refresh(match)
    return serializers.match(match)
