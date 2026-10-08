"""Occupancy reporting for facility operators."""

import datetime as dt
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Facility, Reservation, ReservationSlot
from ..timeutil import QUANTUM_MINUTES, at_local_minute, zone
from . import booking

MAX_REPORT_DAYS = 92


def _percent(used: int, available: int) -> float:
    return round(100 * used / available, 1) if available else 0.0


def occupancy(db: Session, facility: Facility, date_from: dt.date, date_to: dt.date) -> schemas.OccupancyOut:
    """How much of each bookable unit's open time is booked or blocked between two local dates (inclusive)."""
    tz = zone(facility.timezone)
    # Report on leaf units: a full court's bookings already show up on each of its halves.
    units = [resource for resource in facility.resources if resource.is_active and not resource.children]
    open_per_unit = 0
    day = date_from
    while day <= date_to:
        hours = booking.hours_for(facility, day.weekday())
        if hours:
            open_per_unit += hours.close_minute - hours.open_minute
        day += dt.timedelta(days=1)

    start = at_local_minute(date_from, 0, tz)
    end = at_local_minute(date_to + dt.timedelta(days=1), 0, tz)
    held: Counter[tuple[str, str]] = Counter()
    if units:
        rows = db.execute(
            select(ReservationSlot.unit_resource_id, Reservation.kind, func.count())
            .join(Reservation, Reservation.id == ReservationSlot.reservation_id)
            .where(
                ReservationSlot.unit_resource_id.in_([unit.id for unit in units]),
                ReservationSlot.slot_start >= start,
                ReservationSlot.slot_start < end,
            )
            .group_by(ReservationSlot.unit_resource_id, Reservation.kind)
        ).all()
        for unit_id, kind, count in rows:
            held[(unit_id, kind)] = count * QUANTUM_MINUTES

    resources = [
        schemas.ResourceOccupancy(
            resource_id=unit.id,
            name=unit.name,
            open_minutes=open_per_unit,
            booked_minutes=held[(unit.id, "booking")],
            blocked_minutes=held[(unit.id, "block")],
            occupancy_percent=_percent(held[(unit.id, "booking")], open_per_unit),
        )
        for unit in units
    ]

    statuses = dict(
        db.execute(
            select(Reservation.status, func.count())
            .where(
                Reservation.facility_id == facility.id,
                Reservation.kind == "booking",
                Reservation.start_at >= start,
                Reservation.start_at < end,
            )
            .group_by(Reservation.status)
        ).all()
    )
    value = db.scalar(
        select(func.coalesce(func.sum(Reservation.price_centavos), 0)).where(
            Reservation.facility_id == facility.id,
            Reservation.kind == "booking",
            Reservation.status == "confirmed",
            Reservation.start_at >= start,
            Reservation.start_at < end,
        )
    )
    total_open = open_per_unit * len(units)
    total_booked = sum(item.booked_minutes for item in resources)
    return schemas.OccupancyOut(
        facility_id=facility.id,
        date_from=date_from,
        date_to=date_to,
        open_minutes=total_open,
        booked_minutes=total_booked,
        blocked_minutes=sum(item.blocked_minutes for item in resources),
        occupancy_percent=_percent(total_booked, total_open),
        confirmed_bookings=statuses.get("confirmed", 0),
        pending_bookings=statuses.get("pending", 0),
        cancelled_bookings=statuses.get("cancelled", 0) + statuses.get("rejected", 0),
        booked_value_centavos=int(value or 0),
        resources=resources,
    )
