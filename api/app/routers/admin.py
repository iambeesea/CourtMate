from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import ResourceType, Sport, SportCategory, User
from ..security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

_JSON_FIELDS = ("player_config", "match_format", "scoring_config")


def _check_references(db: Session, category_id: str | None, resource_types: list[str] | None) -> None:
    if category_id is not None and db.get(SportCategory, category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown sport category.")
    if resource_types:
        known = set(db.scalars(select(ResourceType.id).where(ResourceType.id.in_(resource_types))).all())
        if unknown := sorted(set(resource_types) - known):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown resource type: {', '.join(unknown)}.")


def _check_queue(queue_eligible: bool, match_format: dict) -> None:
    if queue_eligible and not match_format.get("queueModes"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A queue-eligible sport needs at least one queue mode.")


@router.post("/sports", response_model=schemas.SportOut, status_code=status.HTTP_201_CREATED)
def create_sport(payload: schemas.SportIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Add a sport to the catalog. No code change or deploy is needed."""
    if db.get(Sport, payload.id) or db.scalar(select(Sport.id).where(Sport.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A sport with that id or name already exists.")
    _check_references(db, payload.category_id, payload.resource_types)
    data = payload.model_dump(exclude=set(_JSON_FIELDS))
    for field in _JSON_FIELDS:
        data[field] = getattr(payload, field).model_dump(by_alias=True)
    _check_queue(payload.queue_eligible, data["match_format"])
    sport = Sport(**data)
    db.add(sport)
    db.commit()
    db.refresh(sport)
    return serializers.sport(sport)


@router.patch("/sports/{sport_id}", response_model=schemas.SportOut)
def update_sport(sport_id: str, payload: schemas.SportPatch, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    sport = db.get(Sport, sport_id)
    if sport is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sport not found.")
    _check_references(db, payload.category_id, payload.resource_types)
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is None:
            continue
        setattr(sport, field, value.model_dump(by_alias=True) if field in _JSON_FIELDS else value)
    _check_queue(sport.queue_eligible, sport.match_format)
    db.commit()
    db.refresh(sport)
    return serializers.sport(sport)
