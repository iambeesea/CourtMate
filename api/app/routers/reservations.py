from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..models import Reservation, Resource, User
from ..security import current_user, staff_role
from ..services import booking
from ..timeutil import to_utc, utcnow

router = APIRouter(prefix="/reservations", tags=["reservations"])

# Stops one account from holding a venue's whole calendar.
MAX_ACTIVE_BOOKINGS = 20


def booking_error(error: booking.BookingError) -> HTTPException:
    return HTTPException(error.status_code, error.message)


def _visible_reservation(db: Session, reservation_id: str, user: User) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None or reservation.kind != "booking":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    if reservation.organizer_user_id != user.id and staff_role(db, reservation.facility_id, user) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    return reservation


@router.post("", response_model=list[schemas.ReservationOut], status_code=status.HTTP_201_CREATED)
def create_reservation(payload: schemas.ReservationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Book a resource. Returns one reservation, or every occurrence of a weekly series."""
    resource = db.get(Resource, payload.resource_id)
    if resource is None or resource.facility.verification_status != "verified":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found.")
    now = utcnow()
    active = db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.organizer_user_id == user.id,
            Reservation.kind == "booking",
            Reservation.status.in_(("pending", "confirmed")),
            Reservation.end_at > now,
        )
    )
    if (active or 0) + payload.repeat_weeks > MAX_ACTIVE_BOOKINGS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You can hold up to {MAX_ACTIVE_BOOKINGS} upcoming reservations at a time.")
    try:
        reservations = booking.create_booking(
            db,
            facility=resource.facility,
            resource=resource,
            organizer=user,
            start_at=to_utc(payload.start_at),
            end_at=to_utc(payload.end_at),
            sport_id=payload.sport_id,
            party_size=payload.party_size,
            note=payload.note.strip(),
            repeat_weeks=payload.repeat_weeks,
            now=now,
        )
        db.commit()
    except booking.BookingError as error:
        db.rollback()
        raise booking_error(error) from error
    return [serializers.reservation(item, now=now) for item in reservations]


@router.get("", response_model=list[schemas.ReservationOut])
def list_my_reservations(
    scope: Literal["upcoming", "past", "all"] = "upcoming",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    now = utcnow()
    query = select(Reservation).where(Reservation.organizer_user_id == user.id, Reservation.kind == "booking")
    if scope == "upcoming":
        query = query.where(Reservation.end_at > now, Reservation.status.in_(("pending", "confirmed"))).order_by(Reservation.start_at)
    elif scope == "past":
        query = query.where((Reservation.end_at <= now) | Reservation.status.in_(("cancelled", "rejected"))).order_by(
            Reservation.start_at.desc()
        )
    else:
        query = query.order_by(Reservation.start_at.desc())
    return [serializers.reservation(item, now=now) for item in db.scalars(query.limit(limit).offset(offset)).all()]


@router.get("/{reservation_id}", response_model=schemas.ReservationOut)
def read_reservation(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serializers.reservation(_visible_reservation(db, reservation_id, user))


@router.post("/{reservation_id}/cancel", response_model=schemas.ReservationOut)
def cancel_reservation(
    reservation_id: str, payload: schemas.CancelIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    reservation = _visible_reservation(db, reservation_id, user)
    try:
        booking.cancel(db, reservation, by=user, reason=(payload.reason if payload else "").strip())
        db.commit()
    except booking.BookingError as error:
        db.rollback()
        raise booking_error(error) from error
    return serializers.reservation(reservation)
