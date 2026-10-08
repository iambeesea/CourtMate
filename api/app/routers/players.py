from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import ActivityLog, Sport, User
from ..security import current_user
from ..services import stats
from ..timeutil import to_utc

router = APIRouter(prefix="/players", tags=["players"])


def _sport(db: Session, sport_id: str) -> Sport:
    sport = db.get(Sport, sport_id)
    if sport is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sport not found.")
    return sport


@router.get("/me/records", response_model=list[schemas.RecordOverview])
def my_records(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The sports this player has any recorded result in, most active first."""
    return stats.overview(db, user)


@router.get("/me/stats", response_model=schemas.StatsOut)
def my_stats(
    sport_id: str | None = Query(default=None, alias="sportId"), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """One sport's record. Without `sportId`, the player's most active sport, then their main sport.

    Figures are computed from recorded matches, logged activities and checked-in attendance.
    A sport with nothing recorded returns `hasData: false` and no figures.
    """
    if sport_id is None:
        records = stats.overview(db, user)
        primary = next((item.sport_id for item in user.sports if item.is_primary), None)
        sport_id = records[0].sport.id if records else primary or (user.sports[0].sport_id if user.sports else "pickleball")
    return stats.stats_for(db, user, _sport(db, sport_id))


@router.get("/me/matches", response_model=list[schemas.MyMatchOut])
def my_matches(
    sport_id: str | None = Query(default=None, alias="sportId"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Match history, newest first."""
    rows = stats.my_matches(db, user.id, sport_id)[::-1][:limit]
    return [serializers.my_match(match, side, stats.result_for(match, side)) for match, side in rows]


@router.get("/me/achievements", response_model=list[schemas.AchievementOut])
def my_achievements(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return stats.achievements(db, user)


@router.get("/me/activities", response_model=list[schemas.ActivityOut])
def my_activities(
    sport_id: str | None = Query(default=None, alias="sportId"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(ActivityLog).where(ActivityLog.user_id == user.id).order_by(ActivityLog.occurred_at.desc())
    if sport_id:
        query = query.where(ActivityLog.sport_id == sport_id)
    return [serializers.activity(item) for item in db.scalars(query.limit(limit)).all()]


@router.post("/me/activities", response_model=schemas.ActivityOut, status_code=status.HTTP_201_CREATED)
def log_activity(payload: schemas.ActivityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Log a run, ride, swim, bowling game or round. The sport decides which measurements are accepted."""
    sport = _sport(db, payload.sport_id)
    occurred_at = to_utc(payload.occurred_at)
    try:
        metrics = stats.validate_activity(sport, payload.metrics, occurred_at)
    except stats.ActivityError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.message) from error
    entry = ActivityLog(user_id=user.id, sport_id=sport.id, occurred_at=occurred_at, metrics=metrics, note=payload.note.strip())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serializers.activity(entry)


@router.delete("/me/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    entry = db.get(ActivityLog, activity_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found.")
    db.delete(entry)
    db.commit()
