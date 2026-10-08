from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import CommunityMember, GeoCity, Sport, Team, TeamMember, User
from ..security import current_user, optional_user

router = APIRouter(prefix="/teams", tags=["teams"])

MAX_TEAM_SIZE = 60


def _team(db: Session, team_id: str) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found.")
    return team


def _detail(db: Session, team: Team, viewer: User | None) -> schemas.TeamDetail:
    db.refresh(team)
    return serializers.team_detail(team, viewer)


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(
    sport_id: str | None = Query(default=None, alias="sportId"),
    community_id: str | None = Query(default=None, alias="communityId"),
    q: str | None = Query(default=None, min_length=2, max_length=80),
    mine: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    query = select(Team)
    if mine:
        if viewer is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
        query = query.where(Team.id.in_(select(TeamMember.team_id).where(TeamMember.user_id == viewer.id)))
    if sport_id:
        query = query.where(Team.sport_id == sport_id)
    if community_id:
        query = query.where(Team.community_id == community_id)
    if q:
        query = query.where(Team.name.ilike(f"%{q.strip()}%"))
    return [serializers.team(item, viewer) for item in db.scalars(query.order_by(Team.name).limit(limit)).unique().all()]


@router.post("", response_model=schemas.TeamDetail, status_code=status.HTTP_201_CREATED)
def create_team(payload: schemas.TeamIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sport = db.get(Sport, payload.sport_id)
    if sport is None or not sport.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown sport.")
    if payload.city_code and db.get(GeoCity, payload.city_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown city or municipality code.")
    if payload.community_id and db.get(CommunityMember, (payload.community_id, user.id)) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Join that community before creating a team in it.")
    team = Team(
        name=payload.name.strip(),
        sport_id=sport.id,
        community_id=payload.community_id,
        captain_user_id=user.id,
        city_code=payload.city_code,
        description=payload.description,
    )
    db.add(team)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"There is already a {sport.name} team with that name.") from None
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="captain"))
    db.commit()
    return _detail(db, team, user)


@router.get("/{team_id}", response_model=schemas.TeamDetail)
def read_team(team_id: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return serializers.team_detail(_team(db, team_id), viewer)


@router.post("/{team_id}/join", response_model=schemas.TeamDetail)
def join_team(team_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id)
    if db.get(TeamMember, (team.id, user.id)) is None:
        if len(team.members) >= MAX_TEAM_SIZE:
            raise HTTPException(status.HTTP_409_CONFLICT, "This team is full.")
        db.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
        db.commit()
    return _detail(db, team, user)


@router.post("/{team_id}/leave", response_model=schemas.TeamDetail)
def leave_team(team_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id)
    membership = db.get(TeamMember, (team.id, user.id))
    if membership is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are not on this team.")
    if membership.role == "captain":
        raise HTTPException(status.HTTP_409_CONFLICT, "The captain cannot leave the team.")
    db.delete(membership)
    db.commit()
    return _detail(db, team, user)


@router.delete("/{team_id}/members/{user_id}", response_model=schemas.TeamDetail)
def remove_team_member(team_id: str, user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id)
    if user.id != team.captain_user_id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the captain can remove players.")
    membership = db.get(TeamMember, (team.id, user_id))
    if membership is None or membership.role == "captain":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found on this team.")
    db.delete(membership)
    db.commit()
    return _detail(db, team, user)
