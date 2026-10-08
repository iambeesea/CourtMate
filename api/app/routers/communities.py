import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import Community, CommunityMember, CommunitySport, GeoCity, Sport, Team, User, new_id
from ..security import current_user, optional_user

router = APIRouter(prefix="/communities", tags=["communities"])

MAX_OWNED = 20


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "community"


def _sports(db: Session, sport_ids: list[str]) -> list[Sport]:
    sports = db.scalars(select(Sport).where(Sport.id.in_(sport_ids), Sport.is_active.is_(True))).all()
    if unknown := sorted(set(sport_ids) - {sport.id for sport in sports}):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown sport: {', '.join(unknown)}.")
    return list(sports)


def _place(db: Session, community: Community, city_code: str | None) -> None:
    if not city_code:
        community.city_code = community.province_code = community.region_code = None
        return
    city = db.get(GeoCity, city_code)
    if city is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown city or municipality code.")
    community.city_code, community.province_code, community.region_code = city.code, city.province_code, city.region_code


def _membership(db: Session, community_id: str, user: User | None) -> CommunityMember | None:
    if user is None:
        return None
    return db.get(CommunityMember, (community_id, user.id))


def visible_community(db: Session, community_id: str, viewer: User | None) -> Community:
    community = db.scalar(select(Community).where(or_(Community.id == community_id, Community.slug == community_id)))
    # Private communities exist only for their members.
    if community is None or (community.visibility == "private" and _membership(db, community.id, viewer) is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Community not found.")
    return community


def _managed(db: Session, community_id: str, user: User) -> Community:
    community = visible_community(db, community_id, user)
    membership = _membership(db, community.id, user)
    if user.role != "admin" and (membership is None or membership.role not in {"owner", "admin"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the community's organisers can do this.")
    return community


def _detail(db: Session, community: Community, viewer: User | None) -> schemas.CommunityDetail:
    db.refresh(community)
    teams = db.scalars(select(Team).where(Team.community_id == community.id).order_by(Team.name)).unique().all()
    return serializers.community_detail(community, list(teams), viewer)


@router.get("", response_model=list[schemas.CommunityOut])
def list_communities(
    sport_id: str | None = Query(default=None, alias="sportId"),
    region_code: str | None = Query(default=None, alias="regionCode"),
    province_code: str | None = Query(default=None, alias="provinceCode"),
    city_code: str | None = Query(default=None, alias="cityCode"),
    q: str | None = Query(default=None, min_length=2, max_length=80),
    mine: bool = Query(default=False, description="Only communities the signed-in player belongs to"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    query = select(Community)
    if mine:
        if viewer is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
        query = query.where(Community.id.in_(select(CommunityMember.community_id).where(CommunityMember.user_id == viewer.id)))
    else:
        query = query.where(Community.visibility == "public")
    if sport_id:
        query = query.where(Community.id.in_(select(CommunitySport.community_id).where(CommunitySport.sport_id == sport_id)))
    if region_code:
        query = query.where(Community.region_code == region_code)
    if province_code:
        query = query.where(Community.province_code == province_code)
    if city_code:
        query = query.where(Community.city_code == city_code)
    if q:
        query = query.where(Community.name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(query.order_by(Community.name).limit(limit).offset(offset)).unique().all()
    return [serializers.community(item, viewer) for item in rows]


@router.post("", response_model=schemas.CommunityDetail, status_code=status.HTTP_201_CREATED)
def create_community(payload: schemas.CommunityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned = db.scalars(select(Community.id).where(Community.owner_user_id == user.id)).all()
    if len(owned) >= MAX_OWNED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You can run up to {MAX_OWNED} communities.")
    name = payload.name.strip()
    community = Community(
        name=name,
        slug=f"{_slug(name)}-{new_id()[:6]}",
        description=payload.description,
        owner_user_id=user.id,
        visibility=payload.visibility,
    )
    _place(db, community, payload.city_code)
    community.sports = _sports(db, payload.sport_ids)
    db.add(community)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A community with that name already exists.") from None
    db.add(CommunityMember(community_id=community.id, user_id=user.id, role="owner"))
    db.commit()
    return _detail(db, community, user)


@router.get("/{community_id}", response_model=schemas.CommunityDetail)
def read_community(community_id: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    community = visible_community(db, community_id, viewer)
    teams = db.scalars(select(Team).where(Team.community_id == community.id).order_by(Team.name)).unique().all()
    return serializers.community_detail(community, list(teams), viewer)


@router.patch("/{community_id}", response_model=schemas.CommunityDetail)
def update_community(community_id: str, payload: schemas.CommunityPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    community = _managed(db, community_id, user)
    if payload.name is not None:
        community.name = payload.name.strip()
    if payload.description is not None:
        community.description = payload.description
    if "city_code" in payload.model_fields_set:
        _place(db, community, payload.city_code)
    if payload.sport_ids is not None:
        community.sports = _sports(db, payload.sport_ids)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A community with that name already exists.") from None
    return _detail(db, community, user)


@router.post("/{community_id}/join", response_model=schemas.CommunityDetail)
def join_community(community_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    community = db.get(Community, community_id)
    if community is None or (community.visibility == "private" and _membership(db, community_id, user) is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Community not found.")
    if _membership(db, community.id, user) is None:
        db.add(CommunityMember(community_id=community.id, user_id=user.id, role="member"))
        db.commit()
    return _detail(db, community, user)


@router.post("/{community_id}/leave", response_model=schemas.CommunityDetail)
def leave_community(community_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    community = visible_community(db, community_id, user)
    membership = _membership(db, community.id, user)
    if membership is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are not a member of this community.")
    if membership.role == "owner":
        raise HTTPException(status.HTTP_409_CONFLICT, "The owner cannot leave their own community.")
    db.delete(membership)
    db.commit()
    return _detail(db, community, user)
