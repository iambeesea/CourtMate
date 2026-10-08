"""Player records, computed on request from recorded results.

Nothing here invents numbers: a statistic appears only when there are rows to
compute it from, and each sport's own configuration decides what is counted.
"""

import datetime as dt
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..models import ActivityLog, CommunityMember, Match, MatchPlayer, PlaySession, SessionParticipant, Sport, User
from ..timeutil import DEFAULT_TIMEZONE, utcnow, zone

MONTHS_SHOWN = 6
MONTH_LABELS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


class ActivityError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def record_type(sport: Sport) -> str:
    kind = (sport.scoring_config or {}).get("kind")
    if kind == "individual":
        return "activities"
    if kind in {"games", "total", "result"}:
        return "matches"
    return "attendance"


def _number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _stat(
    key: str, label: str, value: float, *, decimals: int = 0, unit: str = "", note: str = "", display: str | None = None
) -> schemas.StatValue:
    shown = display if display is not None else _number(value, decimals)
    return schemas.StatValue(key=key, label=label, value=round(value, 3), display=shown, unit=unit, note=note)


def _by_month(moments: list[dt.datetime], now: dt.datetime) -> list[schemas.MonthCount]:
    """Counts for the last six calendar months in Philippine time, oldest first."""
    tz = zone(DEFAULT_TIMEZONE)
    counts = Counter((moment.astimezone(tz).year, moment.astimezone(tz).month) for moment in moments)
    today = now.astimezone(tz)
    months = []
    year, month = today.year, today.month
    for _ in range(MONTHS_SHOWN):
        months.append((year, month))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return [
        schemas.MonthCount(month=f"{year}-{month:02d}", label=MONTH_LABELS[month - 1], count=counts.get((year, month), 0))
        for year, month in reversed(months)
    ]


def _streaks(results: list[str]) -> tuple[str | None, int, int]:
    """(current streak type, current streak length, best winning streak) for results in time order."""
    best = run = 0
    for result in results:
        run = run + 1 if result == "W" else 0
        best = max(best, run)
    if not results:
        return None, 0, 0
    current = 0
    for result in reversed(results):
        if result != results[-1]:
            break
        current += 1
    return results[-1], current, best


def my_matches(db: Session, user_id: str, sport_id: str | None = None) -> list[tuple[Match, int]]:
    """Completed matches the player took part in, oldest first, with the side they played on."""
    query = (
        select(Match, MatchPlayer.side)
        .join(MatchPlayer, MatchPlayer.match_id == Match.id)
        .where(MatchPlayer.user_id == user_id, Match.status == "completed")
        .order_by(Match.completed_at, Match.id)
    )
    if sport_id:
        query = query.where(Match.sport_id == sport_id)
    return [(match, side) for match, side in db.execute(query).unique().all()]


def result_for(match: Match, side: int) -> str:
    if match.is_draw or match.winner_side is None:
        return "D"
    return "W" if match.winner_side == side else "L"


def _match_stats(db: Session, user: User, sport: Sport, now: dt.datetime) -> schemas.StatsOut:
    config = sport.scoring_config or {}
    rows = my_matches(db, user.id, sport.id)
    results = [result_for(match, side) for match, side in rows]
    wins, losses, draws = results.count("W"), results.count("L"), results.count("D")
    streak_type, streak, best = _streaks(results)
    summary: list[schemas.StatValue] = []
    partners: dict[str, list] = {}

    if rows:
        played = len(rows)
        win_rate = round(100 * wins / played)
        summary = [
            _stat("matches", "Matches played", played),
            _stat("wins", "Wins", wins, note=f"{win_rate}% win rate"),
            _stat("losses", "Losses", losses),
        ]
        if config.get("allowDraw"):
            summary.append(_stat("draws", "Draws", draws))
        summary.append(_stat("win_rate", "Win rate", win_rate, unit="%", display=f"{win_rate}%"))

        # Games or sets won, and points/goals/runs scored by the player's side, straight from recorded scores.
        scored = conceded = 0
        counted = False
        for match, side in rows:
            totals = (match.score or {}).get("totals")
            if totals and len(totals) == 2:
                counted = True
                scored += totals[side - 1]
                conceded += totals[2 - side]
        if counted and config.get("kind") == "games":
            label = config.get("gameLabel") or "Games"
            summary.append(_stat("games_won", f"{label} won", scored, note=f"{conceded} lost"))
        elif counted and config.get("kind") == "total":
            unit = (config.get("unit") or "points").capitalize()
            summary.append(_stat("side_scored", f"Team {unit.lower()}", scored, note=f"{conceded} conceded"))

        # Individual stat lines, only where somebody actually recorded them.
        for field in config.get("playerFields", []):
            values = []
            for match, _side in rows:
                line = next((player.stats or {} for player in match.players if player.user_id == user.id), {})
                if field["key"] in line:
                    values.append(line[field["key"]])
            if values:
                average = sum(values) / len(values)
                summary.append(_stat(field["key"], field["label"], sum(values), note=f"{average:.1f} a game over {len(values)} recorded"))

        for match, side in rows:
            for player in match.players:
                if player.side == side and player.user_id != user.id:
                    entry = partners.setdefault(player.user_id, [player.user, 0, 0])
                    entry[1] += 1
                    entry[2] += result_for(match, side) == "W"

    top_partners = sorted(partners.values(), key=lambda entry: (-entry[1], -entry[2], entry[0].display_name))[:3]
    return schemas.StatsOut(
        sport=_summary(sport),
        record_type="matches",
        has_data=bool(rows),
        summary=summary,
        recent_form=results[-5:],
        streak_type=streak_type,
        streak=streak,
        best_win_streak=best,
        by_month=_by_month([match.completed_at for match, _ in rows if match.completed_at], now),
        partners=[schemas.PartnerStat(user=_public(partner), matches=matches, wins=won) for partner, matches, won in top_partners],
        contains_demo_data=any(match.is_demo for match, _ in rows),
    )


def _aggregate(aggregation: dict, logs: list[ActivityLog]) -> schemas.StatValue | None:
    """Apply one of a sport's configured aggregations to a player's activity logs."""
    op = aggregation["op"]
    decimals = aggregation.get("decimals", 0)
    unit = aggregation.get("unit", "")
    label = aggregation["label"]
    key = aggregation["key"]
    if op == "count":
        return _stat(key, label, len(logs))

    if op in {"pace", "speed"}:
        # Only activities that recorded both distance and time can contribute to a rate.
        timed = [log for log in logs if log.metrics.get("distance_km") and log.metrics.get("duration_min")]
        distance = sum(log.metrics["distance_km"] for log in timed)
        minutes = sum(log.metrics["duration_min"] for log in timed)
        if not distance or not minutes:
            return None
        if op == "pace":
            pace = minutes / distance
            whole, seconds = int(pace), round((pace - int(pace)) * 60)
            if seconds == 60:
                whole, seconds = whole + 1, 0
            return _stat(key, label, pace, unit=unit, display=f"{whole}:{seconds:02d}")
        return _stat(key, label, distance / (minutes / 60), decimals=decimals, unit=unit)

    values = [log.metrics[aggregation["field"]] for log in logs if aggregation.get("field") in log.metrics]
    if not values:
        return None
    value = {"sum": sum(values), "avg": sum(values) / len(values), "max": max(values), "min": min(values)}[op]
    return _stat(key, label, value, decimals=decimals, unit=unit)


def _activity_stats(db: Session, user: User, sport: Sport, now: dt.datetime) -> schemas.StatsOut:
    logs = list(
        db.scalars(
            select(ActivityLog).where(ActivityLog.user_id == user.id, ActivityLog.sport_id == sport.id).order_by(ActivityLog.occurred_at)
        ).all()
    )
    summary = []
    if logs:
        for aggregation in (sport.scoring_config or {}).get("aggregations", []):
            if (value := _aggregate(aggregation, logs)) is not None:
                summary.append(value)
    return schemas.StatsOut(
        sport=_summary(sport),
        record_type="activities",
        has_data=bool(logs),
        summary=summary,
        recent_form=[],
        streak_type=None,
        streak=0,
        best_win_streak=0,
        by_month=_by_month([log.occurred_at for log in logs], now),
        partners=[],
        contains_demo_data=any(log.is_demo for log in logs),
    )


def _attended(db: Session, user_id: str, sport_id: str | None = None) -> list[PlaySession]:
    """Finished sessions the player was checked in to. Check-in is what makes attendance reliable."""
    query = (
        select(PlaySession)
        .join(SessionParticipant, SessionParticipant.session_id == PlaySession.id)
        .where(SessionParticipant.user_id == user_id, SessionParticipant.checked_in.is_(True), PlaySession.status == "completed")
        .order_by(PlaySession.start_at)
    )
    if sport_id:
        query = query.where(PlaySession.sport_id == sport_id)
    return list(db.scalars(query).unique().all())


def _attendance_stats(db: Session, user: User, sport: Sport, now: dt.datetime) -> schemas.StatsOut:
    sessions = _attended(db, user.id, sport.id)
    summary = []
    if sessions:
        minutes = sum((session.end_at - session.start_at).total_seconds() / 60 for session in sessions)
        summary = [
            _stat("sessions", "Sessions attended", len(sessions)),
            _stat("hours", "Hours attended", minutes / 60, decimals=1, unit="hr"),
        ]
    return schemas.StatsOut(
        sport=_summary(sport),
        record_type="attendance",
        has_data=bool(sessions),
        summary=summary,
        recent_form=[],
        streak_type=None,
        streak=0,
        best_win_streak=0,
        by_month=_by_month([session.start_at for session in sessions], now),
        partners=[],
        contains_demo_data=any(session.is_demo for session in sessions),
    )


def stats_for(db: Session, user: User, sport: Sport, *, now: dt.datetime | None = None) -> schemas.StatsOut:
    now = now or utcnow()
    builder = {"matches": _match_stats, "activities": _activity_stats, "attendance": _attendance_stats}[record_type(sport)]
    return builder(db, user, sport, now)


def overview(db: Session, user: User) -> list[schemas.RecordOverview]:
    """Every sport the player has any record in, most entries first."""
    entries: dict[str, list] = defaultdict(lambda: [0, None])

    def add(sport_id: str, count: int, last: dt.datetime | None) -> None:
        entry = entries[sport_id]
        entry[0] += count
        if last and (entry[1] is None or last > entry[1]):
            entry[1] = last

    for sport_id, count, last in db.execute(
        select(Match.sport_id, func.count(), func.max(Match.completed_at))
        .join(MatchPlayer, MatchPlayer.match_id == Match.id)
        .where(MatchPlayer.user_id == user.id, Match.status == "completed")
        .group_by(Match.sport_id)
    ).all():
        add(sport_id, count, _aware(last))
    for sport_id, count, last in db.execute(
        select(ActivityLog.sport_id, func.count(), func.max(ActivityLog.occurred_at))
        .where(ActivityLog.user_id == user.id)
        .group_by(ActivityLog.sport_id)
    ).all():
        add(sport_id, count, _aware(last))
    for session in _attended(db, user.id):
        sport = db.get(Sport, session.sport_id)
        if sport and record_type(sport) == "attendance":
            add(session.sport_id, 1, session.start_at)

    rows = []
    for sport_id, (count, last) in entries.items():
        sport = db.get(Sport, sport_id)
        if sport:
            rows.append(schemas.RecordOverview(sport=_summary(sport), record_type=record_type(sport), entries=count, last_played_at=last))
    return sorted(rows, key=lambda row: (-row.entries, row.sport.name))


def _aware(value) -> dt.datetime | None:
    """Aggregate functions bypass the column type, so SQLite hands back text or a naive datetime."""
    if value is None:
        return None
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def achievements(db: Session, user: User) -> list[schemas.AchievementOut]:
    """Badges earned from real records. Unearned badges are simply absent."""
    earned: list[schemas.AchievementOut] = []
    rows = my_matches(db, user.id)
    by_sport: dict[str, list[str]] = defaultdict(list)
    for match, side in rows:
        by_sport[match.sport_id].append(result_for(match, side))
    best = max((_streaks(results)[2] for results in by_sport.values()), default=0)
    logged = db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.user_id == user.id)) or 0
    active_sports = len(overview(db, user))

    if rows or logged:
        earned.append(schemas.AchievementOut(id="first_result", label="On the board", description="Recorded a first result."))
    if best >= 3:
        earned.append(schemas.AchievementOut(id="hot_streak", label="Hot streak", description=f"Won {best} matches in a row."))
    if len(rows) + logged >= 10:
        earned.append(schemas.AchievementOut(id="regular", label="Regular", description=f"{len(rows) + logged} results recorded."))
    if active_sports >= 2:
        earned.append(schemas.AchievementOut(id="multi_sport", label="Multi-sport", description=f"Records in {active_sports} sports."))
    if db.scalar(select(func.count()).select_from(CommunityMember).where(CommunityMember.user_id == user.id)):
        earned.append(schemas.AchievementOut(id="community_player", label="Community player", description="Member of a community."))
    hosted = db.scalar(
        select(func.count()).select_from(PlaySession).where(PlaySession.host_user_id == user.id, PlaySession.status == "completed")
    )
    if hosted:
        earned.append(
            schemas.AchievementOut(id="host", label="Host", description=f"Hosted {hosted} finished session{'s' if hosted != 1 else ''}.")
        )
    return earned


def validate_activity(
    sport: Sport, metrics: dict[str, float], occurred_at: dt.datetime, *, now: dt.datetime | None = None
) -> dict[str, float]:
    """Check a self-reported activity against the sport's activity fields. Returns the cleaned metrics."""
    now = now or utcnow()
    fields = {field["key"]: field for field in (sport.scoring_config or {}).get("activityFields", [])}
    if not fields:
        raise ActivityError(f"{sport.name} results are recorded as matches or attendance, not as logged activities.")
    if occurred_at > now + dt.timedelta(minutes=5):
        raise ActivityError("An activity cannot be logged before it happens.")
    if occurred_at < now - dt.timedelta(days=366 * 5):
        raise ActivityError("That date is too far in the past.")
    if unknown := sorted(set(metrics) - set(fields)):
        raise ActivityError(f"{sport.name} does not track: {', '.join(unknown)}.")

    cleaned: dict[str, float] = {}
    for key, field in fields.items():
        if key not in metrics:
            if field.get("required", True):
                raise ActivityError(f"{field['label']} is required.")
            continue
        value = metrics[key]
        if field.get("type") == "integer":
            if value != int(value):
                raise ActivityError(f"{field['label']} must be a whole number.")
            value = int(value)
        low, high = field.get("min"), field.get("max")
        if (low is not None and value < low) or (high is not None and value > high):
            raise ActivityError(
                f"{field['label']} must be between {low:g} and {high:g} {field.get('unit', '')}.".replace("  ", " ").strip()
            )
        cleaned[key] = value
    return cleaned


def _summary(sport: Sport) -> schemas.SportSummary:
    return schemas.SportSummary(id=sport.id, name=sport.name, icon=sport.icon, category_id=sport.category_id)


def _public(user: User) -> schemas.PublicUser:
    from ..serializers import public_user

    return public_user(user)
