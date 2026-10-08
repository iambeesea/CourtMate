from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import ResourceType, Sport, SportCategory

router = APIRouter(tags=["catalog"])


@router.get("/sports/categories", response_model=list[schemas.CategoryOut])
def read_categories(db: Session = Depends(get_db)):
    return db.scalars(select(SportCategory).order_by(SportCategory.sort_order, SportCategory.name)).all()


@router.get("/sports", response_model=list[schemas.SportOut])
def read_sports(
    category: str | None = Query(default=None, description="Category id"),
    bookable: bool | None = Query(default=None, description="Only sports that book facility resources"),
    queue: bool | None = Query(default=None, description="Only sports that support live queues"),
    db: Session = Depends(get_db),
):
    query = select(Sport).where(Sport.is_active.is_(True)).order_by(Sport.sort_order, Sport.name)
    if category:
        query = query.where(Sport.category_id == category)
    if bookable is not None:
        query = query.where(Sport.booking_eligible.is_(bookable))
    if queue is not None:
        query = query.where(Sport.queue_eligible.is_(queue))
    return [serializers.sport(item) for item in db.scalars(query).all()]


@router.get("/sports/{sport_id}", response_model=schemas.SportOut)
def read_sport(sport_id: str, db: Session = Depends(get_db)):
    sport = db.get(Sport, sport_id)
    if sport is None or not sport.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sport not found.")
    return serializers.sport(sport)


@router.get("/resource-types", response_model=list[schemas.ResourceTypeOut])
def read_resource_types(db: Session = Depends(get_db)):
    return db.scalars(select(ResourceType).order_by(ResourceType.sort_order, ResourceType.name)).all()
