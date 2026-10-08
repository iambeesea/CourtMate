"""Open-play sessions: creation, capacity, waitlists, approvals and live queues.

Capacity is enforced by an atomic conditional UPDATE on `confirmed_count`
(backed by a CHECK constraint), so concurrent joins cannot overfill a session.
"""

import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import schemas
from ..models import (
    CommunityMember,
    Facility,
    Match,
    MatchPlayer,
    PlaySession,
    Reservation,
    Resource,
    SessionParticipant,
    Sport,
    User,
    new_id,
)
from ..timeutil import DEFAULT_TIMEZONE, to_utc, utcnow, zone
from . import booking
from .geo import resolve_place
from .notifications import notify, notify_many
from .scoring import ScoreError, player_stat_lines, score_match

ACTIVE_STATUSES = ("confirmed", "waitlisted", "pending")
MAX_UPCOMING_HOSTED = 40
MAX_SESSION_HOURS = 24
NO_SYNC = {"synchronize_session": False}


class SessionError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def link(session: PlaySession) -> str:
    return f"/sessions/{session.id}"


def kind_label(sport: Sport, kind: str) -> str:
    custom = (sport.match_format or {}).get("kindLabels", {}).get(kind)
    return custom or kind.replace("_", " ").capitalize()


def team_format(sport: Sport, format_id: str) -> dict | None:
    formats = (sport.player_config or {}).get("teamFormats", [])
    return next((item for item in formats if item["id"] == format_id), formats[0] if formats else None)


def players_per_match(session: PlaySession) -> int:
    chosen = team_format(session.sport, session.team_format)
    return 2 * (chosen["playersPerSide"] if chosen else 1)


def can_manage(session: PlaySession, user: User | None) -> bool:
    return user is not None and (user.id == session.host_user_id or user.role == "admin")


def participant_for(db: Session, session_id: str, user_id: str) -> SessionParticipant | None:
    return db.scalar(select(SessionParticipant).where(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id))


# --- capacity -----------------------------------------------------------------


def _claim_spot(db: Session, session_id: str) -> bool:
    """Take one confirmed place if any is left. Atomic, so two joiners cannot both take the last place."""
    result = db.execute(
        update(PlaySession)
        .where(PlaySession.id == session_id, PlaySession.confirmed_count < PlaySession.capacity)
        .values(confirmed_count=PlaySession.confirmed_count + 1),
        execution_options=NO_SYNC,
    )
    return result.rowcount == 1


def _free_spot(db: Session, session_id: str) -> None:
    db.execute(
        update(PlaySession)
        .where(PlaySession.id == session_id, PlaySession.confirmed_count > 0)
        .values(confirmed_count=PlaySession.confirmed_count - 1),
        execution_options=NO_SYNC,
    )


def _next_waitlisted(db: Session, session_id: str) -> SessionParticipant | None:
    return db.scalar(
        select(SessionParticipant)
        .where(SessionParticipant.session_id == session_id, SessionParticipant.status == "waitlisted")
        .order_by(SessionParticipant.joined_at, SessionParticipant.id)
        .limit(1)
    )


def _confirm_from_waitlist(db: Session, session: PlaySession, candidate: SessionParticipant) -> bool:
    result = db.execute(
        update(SessionParticipant)
        .where(SessionParticipant.id == candidate.id, SessionParticipant.status == "waitlisted")
        .values(status="confirmed"),
        execution_options=NO_SYNC,
    )
    if result.rowcount != 1:
        return False
    db.refresh(candidate)
    notify(db, candidate.user_id, "waitlist_promoted", "You’re in!", f"A spot opened up in {session.title}.", link(session))
    return True


def _hand_over_spot(db: Session, session: PlaySession) -> None:
    """A confirmed place was vacated: give it to the first waitlisted player, or release it."""
    while (candidate := _next_waitlisted(db, session.id)) is not None:
        if _confirm_from_waitlist(db, session, candidate):
            return
    _free_spot(db, session.id)


def _fill_from_waitlist(db: Session, session: PlaySession) -> None:
    """After capacity grows, move waitlisted players into the new places in order."""
    while (candidate := _next_waitlisted(db, session.id)) is not None:
        if not _claim_spot(db, session.id):
            return
        if not _confirm_from_waitlist(db, session, candidate):
            _free_spot(db, session.id)


def _vacate(db: Session, session: PlaySession, participant: SessionParticipant, new_status: str) -> None:
    was_confirmed = participant.status == "confirmed"
    participant.status = new_status
    participant.queue_state = "idle"
    participant.queued_at = None
    db.flush()
    if was_confirmed:
        _hand_over_spot(db, session)
    db.refresh(session)


# --- creating and editing -----------------------------------------------------


def _check_times(start_at: dt.datetime, end_at: dt.datetime, now: dt.datetime) -> None:
    if end_at <= start_at:
        raise SessionError("The end time must be after the start time.", 422)
    if start_at < now:
        raise SessionError("Sessions must start in the future.", 422)
    if end_at - start_at > dt.timedelta(hours=MAX_SESSION_HOURS):
        raise SessionError(f"A session can run for at most {MAX_SESSION_HOURS} hours.", 422)
    if start_at > now + dt.timedelta(days=366):
        raise SessionError("Sessions can be scheduled up to a year ahead.", 422)


def _check_sport_rules(sport: Sport, *, kind: str, skill_level: str, format_id: str, queue_mode: str) -> None:
    """A sport's player limits describe one match; a session can hold many matches' worth of people."""
    rules = sport.match_format or {}
    players = sport.player_config or {}
    if kind not in rules.get("sessionKinds", []):
        raise SessionError(f"{sport.name} does not use that kind of session.", 422)
    if skill_level not in rules.get("skillLevels", []):
        raise SessionError(f"Choose one of {sport.name}'s skill levels.", 422)
    if format_id and format_id not in {item["id"] for item in players.get("teamFormats", [])}:
        raise SessionError(f"{sport.name} is not played in that format.", 422)
    if queue_mode != "none" and (not sport.queue_eligible or queue_mode not in rules.get("queueModes", [])):
        raise SessionError(f"{sport.name} sessions do not use that queue.", 422)


def create(db: Session, host: User, data: schemas.SessionIn, *, now: dt.datetime | None = None) -> list[PlaySession]:
    """Create one session or a weekly series inside the caller's transaction."""
    now = now or utcnow()
    sport = db.get(Sport, data.sport_id)
    if sport is None or not sport.is_active:
        raise SessionError("Unknown sport.", 422)
    start_at, end_at = to_utc(data.start_at), to_utc(data.end_at)
    _check_times(start_at, end_at, now)
    _check_sport_rules(sport, kind=data.kind, skill_level=data.skill_level, format_id=data.team_format, queue_mode=data.queue_mode)

    facility: Facility | None = None
    resource: Resource | None = None
    if data.facility_id:
        facility = db.get(Facility, data.facility_id)
        if facility is None or facility.verification_status != "verified":
            raise SessionError("Unknown facility.", 422)
        if sport.id not in {item.id for item in facility.sports}:
            raise SessionError(f"{facility.name} is not set up for {sport.name}.", 422)
        if data.resource_id:
            resource = db.get(Resource, data.resource_id)
            if resource is None or resource.facility_id != facility.id:
                raise SessionError("That resource is not at this facility.", 422)
        place = {
            "venue_name": facility.name,
            "region_code": facility.region_code,
            "province_code": facility.province_code,
            "city_code": facility.city_code,
            "barangay_code": facility.barangay_code,
            "latitude": facility.latitude,
            "longitude": facility.longitude,
            "timezone": facility.timezone,
        }
    else:
        if not data.city_code or not data.venue_name.strip():
            raise SessionError("Choose a facility, or give the city and the name of the place to meet.", 422)
        city, barangay = resolve_place(db, data.city_code, data.barangay_code)
        place = {
            "venue_name": data.venue_name.strip(),
            "region_code": city.region_code,
            "province_code": city.province_code,
            "city_code": city.code,
            "barangay_code": barangay.code if barangay else None,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "timezone": DEFAULT_TIMEZONE,
        }

    if data.community_id:
        member = db.scalar(
            select(CommunityMember.role).where(CommunityMember.community_id == data.community_id, CommunityMember.user_id == host.id)
        )
        if member is None:
            raise SessionError("Join that community before hosting for it.", 403)

    upcoming = db.scalar(
        select(func.count())
        .select_from(PlaySession)
        .where(PlaySession.host_user_id == host.id, PlaySession.status.in_(("scheduled", "live")), PlaySession.end_at > now)
    )
    if (upcoming or 0) + data.repeat_weeks > MAX_UPCOMING_HOSTED:
        raise SessionError(f"You can host up to {MAX_UPCOMING_HOSTED} upcoming sessions at a time.")

    tz = zone(place["timezone"])
    local_start = start_at.astimezone(tz)
    duration = end_at - start_at
    series_id = new_id() if data.repeat_weeks > 1 else None
    uses_routes = bool((sport.match_format or {}).get("usesRoutes"))
    sessions: list[PlaySession] = []

    for week in range(data.repeat_weeks):
        occurrence_local = dt.datetime.combine(local_start.date() + dt.timedelta(weeks=week), local_start.time(), tzinfo=tz)
        occurrence_start = occurrence_local.astimezone(dt.UTC)
        session = PlaySession(
            title=data.title.strip(),
            description=data.description,
            kind=data.kind,
            sport_id=sport.id,
            facility_id=facility.id if facility else None,
            host_user_id=host.id,
            community_id=data.community_id,
            series_id=series_id,
            start_at=occurrence_start,
            end_at=occurrence_start + duration,
            capacity=data.capacity,
            min_players=data.min_players,
            skill_level=data.skill_level,
            team_format=data.team_format,
            gender_eligibility=data.gender_eligibility,
            fee_centavos=data.fee_centavos,
            join_policy=data.join_policy,
            queue_mode=data.queue_mode,
            courts_in_play=data.courts_in_play if data.queue_mode != "none" else 1,
            meetup_note=data.meetup_note.strip(),
            route_name=data.route_name.strip() if uses_routes else "",
            route_distance_km=data.route_distance_km if uses_routes else None,
            **place,
        )
        if facility and resource:
            # Raises BookingError if the venue is not free; the caller rolls everything back.
            [reservation] = booking.create_booking(
                db,
                facility=facility,
                resource=resource,
                organizer=host,
                start_at=session.start_at,
                end_at=session.end_at,
                sport_id=sport.id,
                party_size=min(data.capacity, resource.capacity),
                note=f"Session: {session.title}",
                now=now,
            )
            session.reservation_id = reservation.id
        db.add(session)
        db.flush()
        if data.host_plays:
            db.add(SessionParticipant(session_id=session.id, user_id=host.id, status="confirmed", joined_at=now))
            session.confirmed_count = 1
        sessions.append(session)
    db.flush()
    return sessions


def update_session(db: Session, session: PlaySession, changes: schemas.SessionPatch, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if session.status in {"completed", "cancelled"}:
        raise SessionError("This session is over and can no longer be changed.")
    fields = changes.model_fields_set

    new_start = to_utc(changes.start_at) if changes.start_at else session.start_at
    new_end = to_utc(changes.end_at) if changes.end_at else session.end_at
    rescheduled = (new_start, new_end) != (session.start_at, session.end_at)
    if rescheduled:
        if session.reservation_id:
            raise SessionError("This session holds a venue booking. Cancel it and host a new one to change the time.")
        _check_times(new_start, new_end, now)

    capacity = changes.capacity if changes.capacity is not None else session.capacity
    if capacity < session.confirmed_count:
        raise SessionError(f"{session.confirmed_count} players are already confirmed. Remove players before lowering the limit.")
    min_players = changes.min_players if changes.min_players is not None else session.min_players
    if min_players > capacity:
        raise SessionError("The minimum cannot be more than the player limit.", 422)
    _check_sport_rules(
        session.sport,
        kind=session.kind,
        skill_level=changes.skill_level if changes.skill_level is not None else session.skill_level,
        format_id=session.team_format,
        queue_mode=changes.queue_mode if changes.queue_mode is not None else session.queue_mode,
    )

    for field in ("title", "description", "skill_level", "fee_centavos", "join_policy", "queue_mode", "courts_in_play", "meetup_note"):
        if field in fields and getattr(changes, field) is not None:
            setattr(session, field, getattr(changes, field))
    session.start_at, session.end_at = new_start, new_end
    session.min_players = min_players
    grew = capacity > session.capacity
    session.capacity = capacity
    db.flush()
    if grew:
        _fill_from_waitlist(db, session)
        db.refresh(session)
    if rescheduled:
        notify_many(
            db,
            _active_user_ids(db, session) - {session.host_user_id},
            "session_rescheduled",
            "Schedule change",
            f"{session.title} has a new time. Check the details.",
            link(session),
        )


def _active_user_ids(db: Session, session: PlaySession) -> set[str]:
    return set(
        db.scalars(
            select(SessionParticipant.user_id).where(
                SessionParticipant.session_id == session.id, SessionParticipant.status.in_(ACTIVE_STATUSES)
            )
        ).all()
    )


def cancel_session(db: Session, session: PlaySession, by: User, reason: str = "", *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if session.status in {"completed", "cancelled"}:
        raise SessionError("This session is already over.")
    session.status = "cancelled"
    session.cancelled_at = now
    session.cancel_reason = reason
    _stop_play(db, session, now)
    if session.reservation_id:
        reservation = db.get(Reservation, session.reservation_id)
        if reservation and reservation.status in {"pending", "confirmed"} and reservation.end_at > now:
            booking.cancel(db, reservation, by=by, reason="Session cancelled", now=now)
    notify_many(
        db,
        _active_user_ids(db, session) - {by.id},
        "session_cancelled",
        "Session cancelled",
        f"{session.title} was cancelled." + (f" Reason: {reason}" if reason else ""),
        link(session),
    )


def start_session(db: Session, session: PlaySession, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if session.status != "scheduled":
        raise SessionError("Only a scheduled session can be started.")
    if now < session.start_at - dt.timedelta(hours=2):
        raise SessionError("You can start a session up to two hours before its start time.")
    session.status = "live"


def complete_session(db: Session, session: PlaySession, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if session.status != "live":
        raise SessionError("Only a live session can be finished.")
    session.status = "completed"
    _stop_play(db, session, now)


def _stop_play(db: Session, session: PlaySession, now: dt.datetime) -> None:
    for match in db.scalars(select(Match).where(Match.session_id == session.id, Match.status == "in_progress")).all():
        match.status = "void"
        match.completed_at = now
    db.execute(
        update(SessionParticipant).where(SessionParticipant.session_id == session.id).values(queue_state="idle", queued_at=None),
        execution_options=NO_SYNC,
    )


# --- joining and leaving ------------------------------------------------------


def join(
    db: Session, session: PlaySession, user: User, *, team_id: str | None = None, now: dt.datetime | None = None
) -> SessionParticipant:
    now = now or utcnow()
    if session.status not in {"scheduled", "live"} or session.end_at <= now:
        raise SessionError("This session is no longer open.")
    participant = participant_for(db, session.id, user.id)
    if participant and participant.status in ACTIVE_STATUSES:
        return participant
    if participant and participant.status in {"removed", "declined"}:
        raise SessionError("The host has closed this session to you.", 403)

    needs_approval = session.join_policy == "approval" and user.id != session.host_user_id
    if needs_approval:
        status = "pending"
    else:
        status = "confirmed" if _claim_spot(db, session.id) else "waitlisted"

    if participant is None:
        participant = SessionParticipant(session_id=session.id, user_id=user.id)
        db.add(participant)
    participant.status = status
    participant.joined_at = now
    participant.team_id = team_id
    participant.checked_in = False
    participant.queue_state = "idle"
    participant.queued_at = None
    db.flush()
    db.refresh(session)
    if needs_approval:
        notify(
            db,
            session.host_user_id,
            "join_request",
            "New join request",
            f"{user.display_name} asked to join {session.title}.",
            link(session),
        )
    return participant


def leave(db: Session, session: PlaySession, user: User) -> SessionParticipant:
    participant = participant_for(db, session.id, user.id)
    if participant is None or participant.status not in ACTIVE_STATUSES:
        raise SessionError("You are not in this session.")
    if participant.queue_state == "playing":
        raise SessionError("Finish your current match before leaving.")
    _vacate(db, session, participant, "left")
    return participant


def decide(db: Session, session: PlaySession, participant: SessionParticipant, *, approve: bool) -> None:
    if participant.status != "pending":
        raise SessionError("That request has already been handled.")
    if not approve:
        participant.status = "declined"
        notify(
            db,
            participant.user_id,
            "join_declined",
            "Request declined",
            f"The host of {session.title} declined your request.",
            link(session),
        )
        return
    participant.status = "confirmed" if _claim_spot(db, session.id) else "waitlisted"
    db.flush()
    db.refresh(session)
    body = (
        f"You’re confirmed for {session.title}."
        if participant.status == "confirmed"
        else f"{session.title} is full, so you’re on the waitlist."
    )
    notify(db, participant.user_id, "join_approved", "Request approved", body, link(session))


def remove(db: Session, session: PlaySession, participant: SessionParticipant) -> None:
    if participant.status not in ACTIVE_STATUSES:
        raise SessionError("That player is not in this session.")
    if participant.user_id == session.host_user_id:
        raise SessionError("The host cannot be removed.")
    if participant.queue_state == "playing":
        raise SessionError("Wait for their match to finish, or void it first.")
    _vacate(db, session, participant, "removed")
    notify(db, participant.user_id, "removed", "Removed from session", f"The host removed you from {session.title}.", link(session))


# --- live queue ---------------------------------------------------------------


def _require_live_queue(session: PlaySession) -> None:
    if session.status != "live":
        raise SessionError("The session has not started yet.")
    if session.queue_mode == "none":
        raise SessionError("This session does not run a queue.")


def check_in(db: Session, session: PlaySession, participant: SessionParticipant, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if session.status != "live":
        raise SessionError("Check-in opens when the host starts the session.")
    if participant.status != "confirmed":
        raise SessionError("Only confirmed players can check in.")
    participant.checked_in = True
    if session.queue_mode != "none" and participant.queue_state == "idle":
        participant.queue_state = "waiting"
        participant.queued_at = now


def set_queue_state(
    db: Session, session: PlaySession, participant: SessionParticipant, state: str, *, now: dt.datetime | None = None
) -> None:
    now = now or utcnow()
    _require_live_queue(session)
    if participant.status != "confirmed" or not participant.checked_in:
        raise SessionError("Check in before joining the queue.")
    if participant.queue_state == "playing":
        raise SessionError("You are on court right now.")
    if state == "waiting" and participant.queue_state != "waiting":
        participant.queue_state = "waiting"
        participant.queued_at = now
    elif state == "idle":
        participant.queue_state = "idle"
        participant.queued_at = None


def _waiting(db: Session, session_id: str, limit: int | None = None) -> list[SessionParticipant]:
    query = (
        select(SessionParticipant)
        .where(
            SessionParticipant.session_id == session_id,
            SessionParticipant.status == "confirmed",
            SessionParticipant.queue_state == "waiting",
        )
        .order_by(SessionParticipant.queued_at, SessionParticipant.id)
    )
    return list(db.scalars(query.limit(limit) if limit else query).all())


def court_label(number: int) -> str:
    return f"Court {number}"


def live_matches(db: Session, session_id: str) -> list[Match]:
    return list(
        db.scalars(select(Match).where(Match.session_id == session_id, Match.status == "in_progress").order_by(Match.started_at)).all()
    )


def call_next(db: Session, session: PlaySession, host: User, *, court: int | None = None, now: dt.datetime | None = None) -> Match:
    """Put the players at the head of the queue onto a free court."""
    now = now or utcnow()
    _require_live_queue(session)
    busy = {match.court_label for match in live_matches(db, session.id)}
    numbers = range(1, session.courts_in_play + 1)
    if court is not None:
        if court not in numbers:
            raise SessionError(f"This session has {session.courts_in_play} courts.", 422)
        if court_label(court) in busy:
            raise SessionError(f"{court_label(court)} is in use.")
    else:
        court = next((number for number in numbers if court_label(number) not in busy), None)
        if court is None:
            raise SessionError("Every court is in use. Record a result to free one.")

    needed = players_per_match(session)
    players = _waiting(db, session.id, needed)
    if len(players) < needed:
        raise SessionError(f"{needed} players need to be waiting; {len(players)} {'is' if len(players) == 1 else 'are'}.")

    match = Match(
        sport_id=session.sport_id,
        session_id=session.id,
        court_label=court_label(court),
        recorded_by_user_id=host.id,
        started_at=now,
        is_demo=session.is_demo,
    )
    db.add(match)
    db.flush()
    half = needed // 2
    for index, participant in enumerate(players):
        db.add(MatchPlayer(match_id=match.id, user_id=participant.user_id, side=1 if index < half else 2))
        participant.queue_state = "playing"
        participant.queued_at = None
    db.flush()
    db.refresh(match)
    return match


def _requeue(db: Session, session: PlaySession, match: Match, *, winner_side: int | None, counted: bool, now: dt.datetime) -> None:
    """Send a finished match's players back to the queue.

    `rotation` sends everyone to the back. `winner_stays` puts the winners at the
    front so they play the next challengers. A voided match puts everyone back in front.
    """
    participants = {
        item.user_id: item
        for item in db.scalars(
            select(SessionParticipant).where(
                SessionParticipant.session_id == session.id, SessionParticipant.user_id.in_([player.user_id for player in match.players])
            )
        ).all()
    }
    head = db.scalar(
        select(func.min(SessionParticipant.queued_at)).where(
            SessionParticipant.session_id == session.id, SessionParticipant.queue_state == "waiting"
        )
    )
    front = (head or now) - dt.timedelta(seconds=len(match.players) + 1)
    # Keep a stable order within each side: whoever joined the session first goes first.
    far_future = now + dt.timedelta(days=1)
    ordered = sorted(
        match.players,
        key=lambda player: (
            player.side,
            participants[player.user_id].joined_at if player.user_id in participants else far_future,
            player.user_id,
        ),
    )
    for index, player in enumerate(ordered):
        participant = participants.get(player.user_id)
        if participant is None:
            continue
        if counted:
            participant.games_played += 1
        if session.status != "live" or participant.status != "confirmed" or not participant.checked_in:
            participant.queue_state, participant.queued_at = "idle", None
            continue
        stays = not counted or (session.queue_mode == "winner_stays" and winner_side is not None and player.side == winner_side)
        base = front if stays else now
        participant.queue_state = "waiting"
        participant.queued_at = base + dt.timedelta(milliseconds=index)


def record_result(db: Session, match: Match, result: schemas.MatchResultIn, by: User, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if match.status != "in_progress":
        raise SessionError("This match already has a result.")
    try:
        score, winner_side, is_draw = score_match(match.sport.scoring_config or {}, result)
        lines = player_stat_lines(match.sport.scoring_config or {}, result.player_stats, {player.user_id for player in match.players})
    except ScoreError as error:
        raise SessionError(error.message, 422) from error
    match.score = score
    match.winner_side = winner_side
    match.is_draw = is_draw
    match.status = "completed"
    match.completed_at = now
    match.recorded_by_user_id = by.id
    for player in match.players:
        player.stats = lines.get(player.user_id, {})
    session = db.get(PlaySession, match.session_id) if match.session_id else None
    if session:
        _requeue(db, session, match, winner_side=winner_side, counted=True, now=now)


def void_match(db: Session, match: Match, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if match.status != "in_progress":
        raise SessionError("Only a match in progress can be voided.")
    match.status = "void"
    match.completed_at = now
    session = db.get(PlaySession, match.session_id) if match.session_id else None
    if session:
        _requeue(db, session, match, winner_side=None, counted=False, now=now)
