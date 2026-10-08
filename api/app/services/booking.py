"""Availability and reservations.

A reservation holds one `reservation_slots` row per 15-minute quantum per unit
resource. That table's primary key is the only thing that decides whether a
booking wins, so two requests for the same time cannot both succeed.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Facility, FacilityHours, Reservation, ReservationSlot, Resource, User, new_id
from ..timeutil import QUANTUM_MINUTES, at_local_minute, is_quantum_aligned, local_date_and_minute, quanta, utcnow, zone

MAX_BLOCK_DAYS = 7


class BookingError(Exception):
    def __init__(self, message: str, *, status_code: int = 422, code: str = "invalid_booking") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class SlotTaken(BookingError):
    def __init__(self, message: str = "That time was just taken. Please pick another slot.") -> None:
        super().__init__(message, status_code=409, code="slot_taken")


@dataclass(frozen=True)
class Slot:
    start_at: dt.datetime
    end_at: dt.datetime
    status: str
    price_centavos: int


def unit_ids(resource: Resource) -> list[str]:
    """The resources whose time a booking of `resource` occupies."""
    return [child.id for child in resource.children] or [resource.id]


def price_for(resource: Resource, start_at: dt.datetime, end_at: dt.datetime) -> int:
    minutes = int((end_at - start_at).total_seconds() // 60)
    return round(resource.hourly_rate_centavos * minutes / 60)


def hours_for(facility: Facility, weekday: int) -> FacilityHours | None:
    return next((item for item in facility.hours if item.weekday == weekday), None)


def is_bookable(facility: Facility) -> bool:
    return facility.verification_status == "verified"


def validate_booking_window(
    facility: Facility, resource: Resource, start_at: dt.datetime, end_at: dt.datetime, *, now: dt.datetime, enforce_rules: bool = True
) -> None:
    """Raise BookingError unless [start_at, end_at) is a time this resource can be booked."""
    if end_at <= start_at:
        raise BookingError("The end time must be after the start time.")
    if not (is_quantum_aligned(start_at) and is_quantum_aligned(end_at)):
        raise BookingError(f"Times must fall on {QUANTUM_MINUTES}-minute marks.")

    minutes = int((end_at - start_at).total_seconds() // 60)
    if minutes % resource.slot_minutes:
        raise BookingError(f"{resource.name} is booked in {resource.slot_minutes}-minute blocks.")

    tz = zone(facility.timezone)
    day, start_minute = local_date_and_minute(start_at, tz)
    hours = hours_for(facility, day.weekday())
    if hours is None:
        raise BookingError("The facility is closed on that day.")
    if start_minute < hours.open_minute or start_minute + minutes > hours.close_minute:
        raise BookingError("That time is outside the facility's opening hours.")
    if (start_minute - hours.open_minute) % resource.slot_minutes:
        raise BookingError(f"Bookings for {resource.name} start every {resource.slot_minutes} minutes from opening time.")

    if not enforce_rules:
        return
    if start_at < now:
        raise BookingError("That time has already passed.")
    if start_at < now + dt.timedelta(minutes=facility.min_notice_minutes):
        raise BookingError(f"This facility needs at least {facility.min_notice_minutes} minutes' notice.")
    if start_at > now + dt.timedelta(days=facility.max_advance_days):
        raise BookingError(f"This facility accepts bookings up to {facility.max_advance_days} days ahead.")
    if minutes < facility.min_booking_minutes:
        raise BookingError(f"The minimum booking here is {facility.min_booking_minutes} minutes.")
    if minutes > facility.max_booking_minutes:
        raise BookingError(f"The maximum booking here is {facility.max_booking_minutes} minutes.")


def taken_quanta(db: Session, units: list[str], start_at: dt.datetime, end_at: dt.datetime) -> dict[tuple[str, dt.datetime], str]:
    """Occupied (unit, slot) pairs in a window, mapped to the kind of reservation holding them."""
    if not units:
        return {}
    rows = db.execute(
        select(ReservationSlot.unit_resource_id, ReservationSlot.slot_start, Reservation.kind)
        .join(Reservation, Reservation.id == ReservationSlot.reservation_id)
        .where(ReservationSlot.unit_resource_id.in_(units), ReservationSlot.slot_start >= start_at, ReservationSlot.slot_start < end_at)
    ).all()
    return {(unit, slot): kind for unit, slot, kind in rows}


def day_availability(
    db: Session, facility: Facility, resources: list[Resource], day: dt.date, *, now: dt.datetime
) -> dict[str, list[Slot]]:
    """Bookable slots for each resource on one local calendar day."""
    hours = hours_for(facility, day.weekday())
    if hours is None:
        return {resource.id: [] for resource in resources}

    tz = zone(facility.timezone)
    open_at = at_local_minute(day, hours.open_minute, tz)
    close_at = at_local_minute(day, hours.close_minute, tz)
    all_units = sorted({unit for resource in resources for unit in unit_ids(resource)})
    taken = taken_quanta(db, all_units, open_at, close_at)
    earliest = now + dt.timedelta(minutes=facility.min_notice_minutes)
    latest = now + dt.timedelta(days=facility.max_advance_days)

    result: dict[str, list[Slot]] = {}
    for resource in resources:
        units = unit_ids(resource)
        step = dt.timedelta(minutes=resource.slot_minutes)
        slots: list[Slot] = []
        cursor = open_at
        while cursor + step <= close_at:
            end = cursor + step
            kinds = {taken[(unit, quantum)] for unit in units for quantum in quanta(cursor, end) if (unit, quantum) in taken}
            if cursor < now:
                state = "past"
            elif "booking" in kinds:
                state = "booked"
            elif "block" in kinds:
                state = "blocked"
            elif not is_bookable(facility) or not resource.is_active or cursor < earliest or cursor > latest:
                state = "closed"
            else:
                state = "available"
            slots.append(Slot(cursor, end, state, price_for(resource, cursor, end)))
            cursor = end
        result[resource.id] = slots
    return result


def _hold(db: Session, reservation: Reservation, resource: Resource) -> None:
    db.add(reservation)
    db.flush()
    db.add_all(
        ReservationSlot(unit_resource_id=unit, slot_start=quantum, reservation_id=reservation.id)
        for unit in unit_ids(resource)
        for quantum in quanta(reservation.start_at, reservation.end_at)
    )
    try:
        db.flush()
    except IntegrityError as error:
        raise SlotTaken() from error


def create_booking(
    db: Session,
    *,
    facility: Facility,
    resource: Resource,
    organizer: User,
    start_at: dt.datetime,
    end_at: dt.datetime,
    sport_id: str | None = None,
    party_size: int = 1,
    note: str = "",
    repeat_weeks: int = 1,
    now: dt.datetime | None = None,
) -> list[Reservation]:
    """Create one booking, or a weekly series, inside the caller's transaction.

    Raises BookingError (the caller must roll back). A series is all-or-nothing.
    """
    now = now or utcnow()
    if not is_bookable(facility):
        raise BookingError("This facility is not accepting bookings yet.", status_code=409, code="facility_unavailable")
    if not resource.is_active:
        raise BookingError("This resource is not available for booking.", status_code=409, code="resource_unavailable")
    if party_size > resource.capacity:
        raise BookingError(f"{resource.name} holds up to {resource.capacity} people.")
    if sport_id and sport_id not in {sport.id for sport in resource.sports}:
        raise BookingError(f"{resource.name} is not set up for that sport.")

    tz = zone(facility.timezone)
    local_start = start_at.astimezone(tz)
    duration = end_at - start_at
    series_id = new_id() if repeat_weeks > 1 else None
    status = "pending" if facility.requires_approval else "confirmed"
    reservations: list[Reservation] = []

    for week in range(repeat_weeks):
        # Add whole days in local time so a weekly booking keeps its wall-clock hour.
        occurrence_local = dt.datetime.combine(local_start.date() + dt.timedelta(weeks=week), local_start.time(), tzinfo=tz)
        occurrence_start = occurrence_local.astimezone(dt.UTC)
        occurrence_end = occurrence_start + duration
        try:
            validate_booking_window(facility, resource, occurrence_start, occurrence_end, now=now)
        except BookingError as error:
            if repeat_weeks == 1:
                raise
            raise BookingError(f"{occurrence_local:%a %d %b}: {error.message}", status_code=error.status_code, code=error.code) from error

        price = price_for(resource, occurrence_start, occurrence_end)
        reservation = Reservation(
            resource_id=resource.id,
            facility_id=facility.id,
            kind="booking",
            organizer_user_id=organizer.id,
            sport_id=sport_id,
            start_at=occurrence_start,
            end_at=occurrence_end,
            status=status,
            price_centavos=price,
            payment_status="pay_at_venue" if price else "not_required",
            party_size=party_size,
            note=note,
            free_cancel_until=occurrence_start - dt.timedelta(hours=facility.cancellation_window_hours),
            series_id=series_id,
        )
        try:
            _hold(db, reservation, resource)
        except SlotTaken as error:
            if repeat_weeks == 1:
                raise
            raise SlotTaken(
                f"{occurrence_local:%a %d %b} at {occurrence_local:%I:%M %p} is already taken, so the series was not booked."
            ) from error
        reservations.append(reservation)
    return reservations


def create_block(
    db: Session, *, facility: Facility, resource: Resource, staff: User, start_at: dt.datetime, end_at: dt.datetime, reason: str = ""
) -> Reservation:
    """Take a resource out of service for a period. Uses the same slot table as bookings."""
    if end_at <= start_at:
        raise BookingError("The end time must be after the start time.")
    if not (is_quantum_aligned(start_at) and is_quantum_aligned(end_at)):
        raise BookingError(f"Times must fall on {QUANTUM_MINUTES}-minute marks.")
    if end_at - start_at > dt.timedelta(days=MAX_BLOCK_DAYS):
        raise BookingError(f"A single block can cover at most {MAX_BLOCK_DAYS} days.")
    reservation = Reservation(
        resource_id=resource.id,
        facility_id=facility.id,
        kind="block",
        organizer_user_id=staff.id,
        start_at=start_at,
        end_at=end_at,
        status="confirmed",
        price_centavos=0,
        payment_status="not_required",
        note=reason,
    )
    try:
        _hold(db, reservation, resource)
    except SlotTaken as error:
        raise SlotTaken("There are bookings in that period. Cancel or move them before blocking the time.") from error
    return reservation


def release(db: Session, reservation: Reservation) -> None:
    """Free the time held by a reservation."""
    db.execute(delete(ReservationSlot).where(ReservationSlot.reservation_id == reservation.id))


def cancel(db: Session, reservation: Reservation, *, by: User, reason: str = "", now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if reservation.status not in {"pending", "confirmed"}:
        raise BookingError("This reservation is no longer active.", status_code=409, code="not_active")
    if reservation.end_at <= now:
        raise BookingError("This reservation has already finished.", status_code=409, code="already_finished")
    by_organizer = by.id == reservation.organizer_user_id
    reservation.late_cancellation = bool(
        by_organizer and reservation.kind == "booking" and reservation.free_cancel_until and now > reservation.free_cancel_until
    )
    reservation.status = "cancelled"
    reservation.cancelled_at = now
    reservation.cancel_reason = reason
    release(db, reservation)


def decide(db: Session, reservation: Reservation, *, approve: bool, by: User, reason: str = "", now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    if reservation.kind != "booking" or reservation.status != "pending":
        raise BookingError("Only pending bookings can be accepted or rejected.", status_code=409, code="not_pending")
    reservation.decided_at = now
    reservation.decided_by_user_id = by.id
    if approve:
        reservation.status = "confirmed"
    else:
        reservation.status = "rejected"
        reservation.cancel_reason = reason
        release(db, reservation)
