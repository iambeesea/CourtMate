import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import Facility, FacilitySport, Resource
from ..services import booking
from ..services.geo import bounding_box, haversine_km
from ..timeutil import utcnow, zone

router = APIRouter(tags=["facilities"])

MAX_RADIUS_KM = 300.0


def public_facility(db: Session, facility_id: str) -> Facility:
    facility = db.scalar(select(Facility).where(or_(Facility.id == facility_id, Facility.slug == facility_id)))
    if facility is None or facility.verification_status != "verified":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facility not found.")
    return facility


def parse_day(value: dt.date | None, facility: Facility) -> dt.date:
    today = utcnow().astimezone(zone(facility.timezone)).date()
    day = value or today
    if day < today - dt.timedelta(days=1) or day > today + dt.timedelta(days=366):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a date within the next year.")
    return day


@router.get("/facilities", response_model=list[schemas.FacilitySummary])
def list_facilities(
    response: Response,
    sport_id: str | None = Query(default=None, alias="sportId"),
    region_code: str | None = Query(default=None, alias="regionCode"),
    province_code: str | None = Query(default=None, alias="provinceCode"),
    city_code: str | None = Query(default=None, alias="cityCode"),
    barangay_code: str | None = Query(default=None, alias="barangayCode"),
    resource_type: str | None = Query(default=None, alias="resourceType"),
    q: str | None = Query(default=None, min_length=2, max_length=80),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=15.0, gt=0, le=MAX_RADIUS_KM, alias="radiusKm"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Verified (and clearly labelled demo) facilities. Pass `lat` and `lng` to search by distance."""
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide both lat and lng, or neither.")

    query = select(Facility).where(Facility.verification_status == "verified")
    if sport_id:
        query = query.where(Facility.id.in_(select(FacilitySport.facility_id).where(FacilitySport.sport_id == sport_id)))
    if resource_type:
        query = query.where(
            Facility.id.in_(select(Resource.facility_id).where(Resource.resource_type_id == resource_type, Resource.is_active.is_(True)))
        )
    if region_code:
        query = query.where(Facility.region_code == region_code)
    if province_code:
        query = query.where(Facility.province_code == province_code)
    if city_code:
        query = query.where(Facility.city_code == city_code)
    if barangay_code:
        query = query.where(Facility.barangay_code == barangay_code)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Facility.name.ilike(pattern), Facility.address_line.ilike(pattern)))

    if lat is not None and lng is not None:
        min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
        query = query.where(Facility.latitude.between(min_lat, max_lat), Facility.longitude.between(min_lng, max_lng))
        nearby = [(haversine_km(lat, lng, item.latitude, item.longitude), item) for item in db.scalars(query).unique().all()]
        nearby = sorted(((distance, item) for distance, item in nearby if distance <= radius_km), key=lambda pair: (pair[0], pair[1].name))
        response.headers["X-Total-Count"] = str(len(nearby))
        return [serializers.facility_summary(item, distance) for distance, item in nearby[offset : offset + limit]]

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    rows = db.scalars(query.order_by(Facility.name).limit(limit).offset(offset)).unique().all()
    return [serializers.facility_summary(item) for item in rows]


@router.get("/facilities/{facility_id}", response_model=schemas.FacilityDetail)
def read_facility(facility_id: str, db: Session = Depends(get_db)):
    return serializers.facility_detail(public_facility(db, facility_id))


@router.get("/facilities/{facility_id}/availability", response_model=schemas.FacilityAvailability)
def facility_availability(
    facility_id: str,
    date: dt.date | None = Query(default=None, description="Calendar day in the facility's time zone. Defaults to today."),
    sport_id: str | None = Query(default=None, alias="sportId"),
    db: Session = Depends(get_db),
):
    facility = public_facility(db, facility_id)
    day = parse_day(date, facility)
    resources = [item for item in facility.resources if item.is_active]
    if sport_id:
        resources = [item for item in resources if sport_id in {sport.id for sport in item.sports}]
    slots = booking.day_availability(db, facility, resources, day, now=utcnow())
    return serializers.availability(facility, day, resources, slots)


@router.get("/resources/{resource_id}/availability", response_model=schemas.FacilityAvailability)
def resource_availability(resource_id: str, date: dt.date | None = Query(default=None), db: Session = Depends(get_db)):
    resource = db.get(Resource, resource_id)
    if resource is None or not resource.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found.")
    facility = public_facility(db, resource.facility_id)
    day = parse_day(date, facility)
    slots = booking.day_availability(db, facility, [resource], day, now=utcnow())
    return serializers.availability(facility, day, [resource], slots)
