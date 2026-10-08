"""ORM rows → response models. Privacy decisions live here: only fields named below leave the API."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import schemas
from .models import Facility, FacilityStaff, GeoBarangay, GeoCity, GeoProvince, GeoRegion, Reservation, Resource, Sport, User
from .services import booking
from .timeutil import minute_label, utcnow


def initials(name: str) -> str:
    parts = [part for part in name.replace("-", " ").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def public_user(user: User) -> schemas.PublicUser:
    return schemas.PublicUser(
        id=user.id,
        display_name=user.display_name,
        initials=initials(user.display_name),
        avatar_color=user.avatar_color,
        is_demo=user.is_demo,
    )


def me(db: Session, user: User) -> schemas.Me:
    managed = db.scalars(select(FacilityStaff.facility_id).where(FacilityStaff.user_id == user.id)).all()
    return schemas.Me(
        **public_user(user).model_dump(),
        email=user.email,
        role=user.role,
        bio=user.bio,
        city=schemas.CityOut.model_validate(user.city) if user.city else None,
        sports=[
            schemas.SportProfile(sport_id=item.sport_id, skill_level=item.skill_level, is_primary=item.is_primary) for item in user.sports
        ],
        managed_facility_ids=list(managed),
        created_at=user.created_at,
    )


def sport_summary(sport: Sport) -> schemas.SportSummary:
    return schemas.SportSummary(id=sport.id, name=sport.name, icon=sport.icon, category_id=sport.category_id)


def sport(sport: Sport) -> schemas.SportOut:
    return schemas.SportOut(
        id=sport.id,
        name=sport.name,
        icon=sport.icon,
        category_id=sport.category_id,
        category=schemas.CategoryOut(id=sport.category.id, name=sport.category.name),
        description=sport.description,
        booking_eligible=sport.booking_eligible,
        queue_eligible=sport.queue_eligible,
        player_config=sport.player_config,
        match_format=sport.match_format,
        scoring_config=sport.scoring_config,
        resource_types=sport.resource_types,
        is_active=sport.is_active,
    )


def _place(row: GeoRegion | GeoProvince | GeoCity | GeoBarangay | None) -> schemas.Place | None:
    return schemas.Place(code=row.code, name=row.name) if row else None


def location(region: GeoRegion, province: GeoProvince | None, city: GeoCity, barangay: GeoBarangay | None) -> schemas.LocationOut:
    return schemas.LocationOut(region=_place(region), province=_place(province), city=_place(city), barangay=_place(barangay))


def resource(item: Resource) -> schemas.ResourceOut:
    return schemas.ResourceOut(
        id=item.id,
        name=item.name,
        resource_type=schemas.ResourceTypeOut(id=item.resource_type.id, name=item.resource_type.name),
        parent_id=item.parent_id,
        child_ids=[child.id for child in item.children],
        description=item.description,
        capacity=item.capacity,
        slot_minutes=item.slot_minutes,
        hourly_rate_centavos=item.hourly_rate_centavos,
        is_active=item.is_active,
        sport_ids=[sport.id for sport in item.sports],
    )


def _facility_fields(facility: Facility, distance_km: float | None) -> dict:
    active = [item for item in facility.resources if item.is_active]
    rates = [item.hourly_rate_centavos for item in active]
    return {
        "id": facility.id,
        "name": facility.name,
        "slug": facility.slug,
        "description": facility.description,
        "address_line": facility.address_line,
        "location": location(facility.region, facility.province, facility.city, facility.barangay),
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "timezone": facility.timezone,
        "amenities": facility.amenities or [],
        "photos": facility.photos or [],
        "sports": [sport_summary(item) for item in facility.sports],
        "resource_count": len(active),
        "from_rate_centavos": min(rates) if rates else None,
        "is_demo": facility.is_demo,
        "verification_status": facility.verification_status,
        "distance_km": round(distance_km, 2) if distance_km is not None else None,
    }


def facility_summary(facility: Facility, distance_km: float | None = None) -> schemas.FacilitySummary:
    return schemas.FacilitySummary(**_facility_fields(facility, distance_km))


def booking_rules(facility: Facility) -> schemas.BookingRules:
    return schemas.BookingRules(
        requires_approval=facility.requires_approval,
        min_notice_minutes=facility.min_notice_minutes,
        max_advance_days=facility.max_advance_days,
        cancellation_window_hours=facility.cancellation_window_hours,
        min_booking_minutes=facility.min_booking_minutes,
        max_booking_minutes=facility.max_booking_minutes,
    )


def hours(facility: Facility) -> list[schemas.HoursOut]:
    return [
        schemas.HoursOut(
            weekday=item.weekday,
            open_minute=item.open_minute,
            close_minute=item.close_minute,
            open_label=minute_label(item.open_minute),
            close_label=minute_label(item.close_minute),
        )
        for item in facility.hours
    ]


def facility_detail(facility: Facility, *, include_inactive: bool = False) -> schemas.FacilityDetail:
    resources = [item for item in facility.resources if include_inactive or item.is_active]
    return schemas.FacilityDetail(
        **_facility_fields(facility, None),
        hours=hours(facility),
        resources=[resource(item) for item in resources],
        booking_rules=booking_rules(facility),
    )


def availability(
    facility: Facility, day: dt.date, resources: list[Resource], slots: dict[str, list[booking.Slot]]
) -> schemas.FacilityAvailability:
    today_hours = booking.hours_for(facility, day.weekday())
    return schemas.FacilityAvailability(
        facility_id=facility.id,
        date=day,
        timezone=facility.timezone,
        is_open=today_hours is not None,
        open_minute=today_hours.open_minute if today_hours else None,
        close_minute=today_hours.close_minute if today_hours else None,
        resources=[
            schemas.ResourceAvailability(
                resource=resource(item),
                slots=[
                    schemas.SlotOut(start_at=slot.start_at, end_at=slot.end_at, status=slot.status, price_centavos=slot.price_centavos)
                    for slot in slots.get(item.id, [])
                ],
            )
            for item in resources
        ],
    )


def reservation(item: Reservation, *, now: dt.datetime | None = None) -> schemas.ReservationOut:
    now = now or utcnow()
    active = item.status in {"pending", "confirmed"}
    status = "completed" if item.status == "confirmed" and item.end_at <= now else item.status
    return schemas.ReservationOut(
        id=item.id,
        kind=item.kind,
        status=status,
        resource=schemas.ReservationResource(
            id=item.resource.id,
            name=item.resource.name,
            resource_type=schemas.ResourceTypeOut(id=item.resource.resource_type.id, name=item.resource.resource_type.name),
        ),
        facility=schemas.ReservationFacility(
            id=item.facility.id,
            name=item.facility.name,
            city_name=item.facility.city.name,
            address_line=item.facility.address_line,
            timezone=item.facility.timezone,
            is_demo=item.facility.is_demo,
        ),
        sport=sport_summary(item.sport) if item.sport else None,
        organizer=public_user(item.organizer),
        start_at=item.start_at,
        end_at=item.end_at,
        price_centavos=item.price_centavos,
        payment_status=item.payment_status,
        party_size=item.party_size,
        note=item.note,
        free_cancel_until=item.free_cancel_until,
        late_cancellation=item.late_cancellation,
        series_id=item.series_id,
        created_at=item.created_at,
        cancelled_at=item.cancelled_at,
        cancel_reason=item.cancel_reason,
        can_cancel=active and item.end_at > now,
    )
