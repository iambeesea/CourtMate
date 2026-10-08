"""Facility operator dashboard.

Every route checks that the caller is staff at the facility in question;
anyone else gets a 404, so facility and reservation ids cannot be probed.
"""

import datetime as dt
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import Facility, FacilityHours, FacilityStaff, Reservation, Resource, ResourceType, Sport, User, new_id
from ..security import current_user, require_facility_staff
from ..services import booking, operators
from ..services.geo import resolve_place
from ..services.notifications import notify
from ..timeutil import to_utc, utcnow, zone

router = APIRouter(prefix="/operator", tags=["operators"])

MAX_FACILITIES_PER_OWNER = 10
MAX_RESOURCES_PER_FACILITY = 200
RULE_FIELDS = (
    "requires_approval",
    "min_notice_minutes",
    "max_advance_days",
    "cancellation_window_hours",
    "min_booking_minutes",
    "max_booking_minutes",
)
TEXT_FIELDS = ("name", "description", "address_line", "contact_name", "contact_email", "contact_phone")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "venue"


def _sports(db: Session, sport_ids: list[str]) -> list[Sport]:
    sports = db.scalars(select(Sport).where(Sport.id.in_(sport_ids), Sport.is_active.is_(True))).all()
    if unknown := sorted(set(sport_ids) - {sport.id for sport in sports}):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown sport: {', '.join(unknown)}.")
    not_bookable = sorted(sport.name for sport in sports if not sport.booking_eligible)
    if not_bookable:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"{', '.join(not_bookable)} sessions meet outdoors and are not booked at a facility."
        )
    return list(sports)


def _set_place(db: Session, facility: Facility, city_code: str, barangay_code: str | None) -> None:
    city, barangay = resolve_place(db, city_code, barangay_code)
    facility.region_code, facility.province_code, facility.city_code = city.region_code, city.province_code, city.code
    facility.barangay_code = barangay.code if barangay else None


def _pending(db: Session, facility_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Reservation)
            .where(
                Reservation.facility_id == facility_id,
                Reservation.kind == "booking",
                Reservation.status == "pending",
                Reservation.end_at > utcnow(),
            )
        )
        or 0
    )


def _view(db: Session, facility: Facility) -> schemas.OperatorFacility:
    db.refresh(facility)
    return serializers.operator_facility(db, facility, _pending(db, facility.id))


def _resource(db: Session, resource_id: str, user: User) -> tuple[Facility, Resource]:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found.")
    return require_facility_staff(db, resource.facility_id, user), resource


def _reservation(db: Session, reservation_id: str, user: User) -> tuple[Facility, Reservation]:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    return require_facility_staff(db, reservation.facility_id, user), reservation


def _when(reservation: Reservation) -> str:
    local = reservation.start_at.astimezone(zone(reservation.facility.timezone))
    return f"{local:%a %d %b}, {local:%I:%M %p}".replace(" 0", " ")


# --- facilities ---------------------------------------------------------------


@router.get("/facilities", response_model=list[schemas.OperatorFacility])
def my_facilities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Facilities the signed-in account manages, whatever their verification status."""
    rows = db.scalars(
        select(Facility)
        .where(Facility.id.in_(select(FacilityStaff.facility_id).where(FacilityStaff.user_id == user.id)))
        .order_by(Facility.name)
    ).unique()
    return [serializers.operator_facility(db, facility, _pending(db, facility.id)) for facility in rows]


@router.post("/facilities", response_model=schemas.OperatorFacility, status_code=status.HTTP_201_CREATED)
def register_facility(payload: schemas.FacilityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Register a facility. It stays private and unbookable until an administrator verifies it."""
    owned = db.scalar(select(func.count()).select_from(Facility).where(Facility.owner_user_id == user.id)) or 0
    if owned >= MAX_FACILITIES_PER_OWNER:
        raise HTTPException(status.HTTP_409_CONFLICT, f"One account can register up to {MAX_FACILITIES_PER_OWNER} facilities.")
    name = payload.name.strip()
    facility = Facility(
        name=name,
        slug=f"{_slug(name)}-{new_id()[:6]}",
        description=payload.description,
        address_line=payload.address_line.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        amenities=payload.amenities,
        owner_user_id=user.id,
        contact_name=payload.contact_name.strip(),
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        verification_status="pending",
    )
    _set_place(db, facility, payload.city_code, payload.barangay_code)
    facility.sports = _sports(db, payload.sport_ids)
    db.add(facility)
    db.flush()
    db.add(FacilityStaff(facility_id=facility.id, user_id=user.id, role="owner"))
    db.commit()
    return _view(db, facility)


@router.get("/facilities/{facility_id}", response_model=schemas.OperatorFacility)
def read_my_facility(facility_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    facility = require_facility_staff(db, facility_id, user)
    return serializers.operator_facility(db, facility, _pending(db, facility.id))


@router.patch("/facilities/{facility_id}", response_model=schemas.OperatorFacility)
def update_my_facility(facility_id: str, payload: schemas.FacilityPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Edit facility details, private contact information and booking rules."""
    facility = require_facility_staff(db, facility_id, user)
    fields = payload.model_fields_set
    for field in (*TEXT_FIELDS, *RULE_FIELDS):
        value = getattr(payload, field)
        if field in fields and value is not None:
            setattr(facility, field, value.strip() if isinstance(value, str) else value)
    if facility.max_booking_minutes < facility.min_booking_minutes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The longest booking cannot be shorter than the shortest.")
    if payload.amenities is not None:
        facility.amenities = payload.amenities
    if payload.photos is not None:
        facility.photos = [photo.model_dump() for photo in payload.photos]
    if "latitude" in fields or "longitude" in fields:
        if (payload.latitude is None) != (payload.longitude is None):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide both latitude and longitude, or neither.")
        facility.latitude, facility.longitude = payload.latitude, payload.longitude
    if payload.city_code is not None:
        # Moving to another city clears the barangay unless a new one is given.
        _set_place(db, facility, payload.city_code, payload.barangay_code)
    elif "barangay_code" in fields:
        _set_place(db, facility, facility.city_code, payload.barangay_code)
    if payload.sport_ids is not None:
        # A sport that a resource is still set up for stays on the facility.
        in_use = {sport.id for resource in facility.resources for sport in resource.sports}
        facility.sports = _sports(db, sorted(set(payload.sport_ids) | in_use))
    db.commit()
    return _view(db, facility)


@router.put("/facilities/{facility_id}/hours", response_model=schemas.OperatorFacility)
def set_opening_hours(facility_id: str, payload: list[schemas.HoursIn], user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Replace the weekly schedule. A weekday that is left out is closed."""
    facility = require_facility_staff(db, facility_id, user)
    if len({item.weekday for item in payload}) != len(payload):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Each weekday can appear once.")
    # Remove the old rows first: the (facility, weekday) key would otherwise collide with the new ones.
    facility.hours.clear()
    db.flush()
    facility.hours = [
        FacilityHours(facility_id=facility.id, weekday=item.weekday, open_minute=item.open_minute, close_minute=item.close_minute)
        for item in payload
    ]
    db.commit()
    return _view(db, facility)


# --- resources ----------------------------------------------------------------


def _resource_sports(db: Session, facility: Facility, sport_ids: list[str]) -> list[Sport]:
    sports = _sports(db, sport_ids)
    known = {sport.id for sport in facility.sports}
    facility.sports = [*facility.sports, *[sport for sport in sports if sport.id not in known]]
    return sports


@router.post("/facilities/{facility_id}/resources", response_model=schemas.OperatorFacility, status_code=status.HTTP_201_CREATED)
def add_resource(facility_id: str, payload: schemas.ResourceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Add a court, field, lane, table, studio, pool or other bookable space."""
    facility = require_facility_staff(db, facility_id, user)
    if len(facility.resources) >= MAX_RESOURCES_PER_FACILITY:
        raise HTTPException(status.HTTP_409_CONFLICT, "This facility has reached its limit of bookable spaces.")
    if db.get(ResourceType, payload.resource_type_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown resource type.")
    if payload.parent_id:
        parent = db.get(Resource, payload.parent_id)
        if parent is None or parent.facility_id != facility.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The parent space must belong to this facility.")
        if parent.parent_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A section cannot itself be divided into sections.")
        if booking.has_active_holds(db, parent):
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{parent.name} has upcoming bookings. Divide it once they are finished or cancelled."
            )
    resource = Resource(
        facility_id=facility.id,
        parent_id=payload.parent_id,
        name=payload.name.strip(),
        resource_type_id=payload.resource_type_id,
        description=payload.description,
        capacity=payload.capacity,
        slot_minutes=payload.slot_minutes,
        hourly_rate_centavos=payload.hourly_rate_centavos,
        sort_order=len(facility.resources),
    )
    resource.sports = _resource_sports(db, facility, payload.sport_ids)
    db.add(resource)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This facility already has a space with that name.") from None
    return _view(db, facility)


@router.patch("/resources/{resource_id}", response_model=schemas.OperatorFacility)
def update_resource(resource_id: str, payload: schemas.ResourcePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Edit a space, change its price, or take it off sale with `isActive: false`."""
    facility, resource = _resource(db, resource_id, user)
    for field in ("name", "description", "capacity", "slot_minutes", "hourly_rate_centavos", "is_active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(resource, field, value.strip() if isinstance(value, str) else value)
    if payload.sport_ids is not None:
        resource.sports = _resource_sports(db, facility, payload.sport_ids)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This facility already has a space with that name.") from None
    return _view(db, facility)


@router.post("/resources/{resource_id}/blocks", response_model=schemas.ReservationOut, status_code=status.HTTP_201_CREATED)
def block_time(resource_id: str, payload: schemas.BlockIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Make a space unavailable for a period (maintenance, a private event). Fails if bookings are in the way."""
    facility, resource = _resource(db, resource_id, user)
    try:
        block = booking.create_block(
            db,
            facility=facility,
            resource=resource,
            staff=user,
            start_at=to_utc(payload.start_at),
            end_at=to_utc(payload.end_at),
            reason=payload.reason.strip(),
        )
        db.commit()
    except booking.BookingError as error:
        db.rollback()
        raise HTTPException(error.status_code, error.message) from error
    db.refresh(block)
    return serializers.reservation(block)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_block(block_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, block = _reservation(db, block_id, user)
    if block.kind != "block":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found.")
    if block.status == "confirmed":
        block.status = "cancelled"
        block.cancelled_at = utcnow()
        booking.release(db, block)
        db.commit()


# --- reservations -------------------------------------------------------------


@router.get("/facilities/{facility_id}/reservations", response_model=list[schemas.ReservationOut])
def facility_reservations(
    facility_id: str,
    scope: Literal["pending", "upcoming", "past", "blocks", "all"] = "upcoming",
    date: dt.date | None = Query(default=None, description="Only reservations starting on this local date"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Booking requests, the upcoming schedule, history, or maintenance blocks for one facility."""
    facility = require_facility_staff(db, facility_id, user)
    now = utcnow()
    query = select(Reservation).where(Reservation.facility_id == facility.id)
    if scope == "blocks":
        query = query.where(Reservation.kind == "block", Reservation.status == "confirmed", Reservation.end_at > now).order_by(
            Reservation.start_at
        )
    else:
        query = query.where(Reservation.kind == "booking")
        if scope == "pending":
            query = query.where(Reservation.status == "pending", Reservation.end_at > now).order_by(Reservation.start_at)
        elif scope == "upcoming":
            query = query.where(Reservation.status.in_(("pending", "confirmed")), Reservation.end_at > now).order_by(Reservation.start_at)
        elif scope == "past":
            query = query.where((Reservation.end_at <= now) | Reservation.status.in_(("cancelled", "rejected"))).order_by(
                Reservation.start_at.desc()
            )
        else:
            query = query.order_by(Reservation.start_at.desc())
    if date:
        tz = zone(facility.timezone)
        start = dt.datetime.combine(date, dt.time(0), tzinfo=tz).astimezone(dt.UTC)
        query = query.where(Reservation.start_at >= start, Reservation.start_at < start + dt.timedelta(days=1))
    return [serializers.reservation(item, now=now) for item in db.scalars(query.limit(limit).offset(offset)).all()]


def _decide(db: Session, reservation_id: str, user: User, *, approve: bool, reason: str) -> schemas.ReservationOut:
    _, reservation = _reservation(db, reservation_id, user)
    try:
        booking.decide(db, reservation, approve=approve, by=user, reason=reason)
    except booking.BookingError as error:
        db.rollback()
        raise HTTPException(error.status_code, error.message) from error
    place = f"{reservation.resource.name} at {reservation.facility.name}, {_when(reservation)}"
    if approve:
        notify(db, reservation.organizer_user_id, "booking_confirmed", "Booking confirmed", f"{place} is confirmed.", "/bookings")
    else:
        notify(
            db,
            reservation.organizer_user_id,
            "booking_rejected",
            "Booking declined",
            f"{place} was declined." + (f" {reason}" if reason else ""),
            "/bookings",
        )
    db.commit()
    db.refresh(reservation)
    return serializers.reservation(reservation)


@router.post("/reservations/{reservation_id}/confirm", response_model=schemas.ReservationOut)
def confirm_reservation(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _decide(db, reservation_id, user, approve=True, reason="")


@router.post("/reservations/{reservation_id}/reject", response_model=schemas.ReservationOut)
def reject_reservation(
    reservation_id: str, payload: schemas.CancelIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Decline a pending request. The time becomes available again."""
    return _decide(db, reservation_id, user, approve=False, reason=(payload.reason if payload else "").strip())


@router.post("/reservations/{reservation_id}/cancel", response_model=schemas.ReservationOut)
def cancel_reservation_as_venue(
    reservation_id: str, payload: schemas.CancelIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Cancel a customer's booking from the venue side. The customer is told, with the reason."""
    _, reservation = _reservation(db, reservation_id, user)
    if reservation.kind != "booking":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    reason = (payload.reason if payload else "").strip()
    try:
        booking.cancel(db, reservation, by=user, reason=reason)
    except booking.BookingError as error:
        db.rollback()
        raise HTTPException(error.status_code, error.message) from error
    notify(
        db,
        reservation.organizer_user_id,
        "booking_cancelled",
        "Booking cancelled by the venue",
        f"{reservation.resource.name} at {reservation.facility.name}, {_when(reservation)}, was cancelled."
        + (f" {reason}" if reason else ""),
        "/bookings",
    )
    db.commit()
    db.refresh(reservation)
    return serializers.reservation(reservation)


@router.get("/facilities/{facility_id}/availability", response_model=schemas.FacilityAvailability)
def facility_schedule(
    facility_id: str,
    date: dt.date | None = Query(default=None, description="Calendar day in the facility's time zone. Defaults to today."),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The day's schedule for every space, including ones that are off sale. Works before the facility is verified."""
    facility = require_facility_staff(db, facility_id, user)
    day = date or utcnow().astimezone(zone(facility.timezone)).date()
    resources = list(facility.resources)
    return serializers.availability(facility, day, resources, booking.day_availability(db, facility, resources, day, now=utcnow()))


# --- reporting ----------------------------------------------------------------


@router.get("/facilities/{facility_id}/occupancy", response_model=schemas.OccupancyOut)
def facility_occupancy(
    facility_id: str,
    date_from: dt.date | None = Query(default=None, alias="from"),
    date_to: dt.date | None = Query(default=None, alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Share of open time that is booked, per space, between two local dates. Defaults to the next seven days."""
    facility = require_facility_staff(db, facility_id, user)
    today = utcnow().astimezone(zone(facility.timezone)).date()
    date_from = date_from or today
    date_to = date_to or date_from + dt.timedelta(days=6)
    if date_to < date_from or (date_to - date_from).days >= operators.MAX_REPORT_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose a range of up to {operators.MAX_REPORT_DAYS} days.")
    return operators.occupancy(db, facility, date_from, date_to)
