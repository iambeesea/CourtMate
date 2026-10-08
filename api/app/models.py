"""Relational schema for CourtMate.

Sports, resource types and locations are rows, not enums, so new ones can be
added without a code change. See docs/ARCHITECTURE.md.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")

USER_ROLES = ("player", "admin")
VERIFICATION_STATUSES = ("pending", "verified", "rejected", "suspended")
STAFF_ROLES = ("owner", "manager")
RESERVATION_KINDS = ("booking", "block")
RESERVATION_STATUSES = ("pending", "confirmed", "rejected", "cancelled")
PAYMENT_STATUSES = ("not_required", "pay_at_venue", "paid", "refunded")
SESSION_KINDS = ("open_play", "pickup_game", "class", "sparring", "group_activity", "tee_time", "challenge", "tournament", "event")
SESSION_STATUSES = ("scheduled", "live", "completed", "cancelled")
JOIN_POLICIES = ("open", "approval")
QUEUE_MODES = ("none", "rotation", "winner_stays")
GENDER_ELIGIBILITY = ("open", "women", "men", "mixed")
PARTICIPANT_STATUSES = ("confirmed", "waitlisted", "pending", "left", "removed", "declined")
QUEUE_STATES = ("idle", "waiting", "playing")
MATCH_STATUSES = ("in_progress", "completed", "void")
ACTIVITY_SOURCES = ("self_reported", "organizer_recorded")
COMMUNITY_ROLES = ("owner", "admin", "member")
COMMUNITY_VISIBILITY = ("public", "private")
TEAM_ROLES = ("captain", "member")


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def one_of(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(f"{column} IN ({', '.join(repr(value) for value in values)})", name=name)


# --- accounts ---------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (one_of("role", USER_ROLES, "role"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="player")
    bio: Mapped[str] = mapped_column(Text, default="")
    city_code: Mapped[str | None] = mapped_column(ForeignKey("geo_cities.code"))
    avatar_color: Mapped[str] = mapped_column(String(9), default="#1f3b73")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    sports: Mapped[list["UserSport"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    city: Mapped["GeoCity | None"] = relationship(lazy="joined")


class UserSport(Base):
    """A player's self-declared profile for one sport."""

    __tablename__ = "user_sports"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id", ondelete="CASCADE"), primary_key=True)
    skill_level: Mapped[str] = mapped_column(String(40), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)


# --- sport catalog ----------------------------------------------------------


class SportCategory(Base):
    __tablename__ = "sport_categories"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("sport_categories.id"), index=True)
    icon: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    booking_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    queue_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    player_config: Mapped[dict] = mapped_column(JSONType, default=dict)
    match_format: Mapped[dict] = mapped_column(JSONType, default=dict)
    scoring_config: Mapped[dict] = mapped_column(JSONType, default=dict)
    resource_types: Mapped[list] = mapped_column(JSONType, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[SportCategory] = relationship(lazy="joined")


class ResourceType(Base):
    __tablename__ = "resource_types"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# --- Philippine Standard Geographic Code ------------------------------------


class GeoRegion(Base):
    __tablename__ = "geo_regions"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    region_name: Mapped[str] = mapped_column(String(120))
    island_group: Mapped[str] = mapped_column(String(20))


class GeoProvince(Base):
    __tablename__ = "geo_provinces"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    region_code: Mapped[str] = mapped_column(ForeignKey("geo_regions.code"), index=True)


class GeoCity(Base):
    """A city or municipality. Independent cities and all of NCR have no province."""

    __tablename__ = "geo_cities"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    region_code: Mapped[str] = mapped_column(ForeignKey("geo_regions.code"), index=True)
    province_code: Mapped[str | None] = mapped_column(ForeignKey("geo_provinces.code"), index=True)
    is_city: Mapped[bool] = mapped_column(Boolean, default=False)


class GeoBarangay(Base):
    __tablename__ = "geo_barangays"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city_code: Mapped[str] = mapped_column(ForeignKey("geo_cities.code"), index=True)


# --- facilities and bookable resources ---------------------------------------


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        one_of("verification_status", VERIFICATION_STATUSES, "verification_status"),
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="latitude_range"),
        CheckConstraint("longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="longitude_range"),
        CheckConstraint("min_notice_minutes >= 0", name="min_notice_non_negative"),
        CheckConstraint("max_advance_days BETWEEN 1 AND 365", name="max_advance_range"),
        CheckConstraint("cancellation_window_hours >= 0", name="cancellation_window_non_negative"),
        CheckConstraint("min_booking_minutes > 0 AND max_booking_minutes >= min_booking_minutes", name="booking_duration_range"),
        Index("ix_facilities_location", "region_code", "province_code", "city_code"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    address_line: Mapped[str] = mapped_column(String(255), default="")
    region_code: Mapped[str] = mapped_column(ForeignKey("geo_regions.code"))
    province_code: Mapped[str | None] = mapped_column(ForeignKey("geo_provinces.code"))
    city_code: Mapped[str] = mapped_column(ForeignKey("geo_cities.code"))
    barangay_code: Mapped[str | None] = mapped_column(ForeignKey("geo_barangays.code"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila")
    amenities: Mapped[list] = mapped_column(JSONType, default=list)
    photos: Mapped[list] = mapped_column(JSONType, default=list)

    verification_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    # Private to the operator and administrators. Never serialised publicly.
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    contact_email: Mapped[str] = mapped_column(String(254), default="")
    contact_phone: Mapped[str] = mapped_column(String(40), default="")
    verification_notes: Mapped[str] = mapped_column(Text, default="")

    # Booking rules.
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    min_notice_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_advance_days: Mapped[int] = mapped_column(Integer, default=30)
    cancellation_window_hours: Mapped[int] = mapped_column(Integer, default=24)
    min_booking_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_booking_minutes: Mapped[int] = mapped_column(Integer, default=240)

    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    region: Mapped[GeoRegion] = relationship(lazy="joined")
    province: Mapped[GeoProvince | None] = relationship(lazy="joined")
    city: Mapped[GeoCity] = relationship(lazy="joined")
    barangay: Mapped[GeoBarangay | None] = relationship(lazy="joined")
    hours: Mapped[list["FacilityHours"]] = relationship(cascade="all, delete-orphan", order_by="FacilityHours.weekday", lazy="selectin")
    resources: Mapped[list["Resource"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", order_by="Resource.sort_order, Resource.name", lazy="selectin"
    )
    sports: Mapped[list[Sport]] = relationship(secondary="facility_sports", order_by="Sport.sort_order", lazy="selectin")
    staff: Mapped[list["FacilityStaff"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class FacilitySport(Base):
    __tablename__ = "facility_sports"

    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), primary_key=True, index=True)


class FacilityStaff(Base):
    __tablename__ = "facility_staff"
    __table_args__ = (one_of("role", STAFF_ROLES, "role"),)

    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="manager")


class FacilityHours(Base):
    """Opening hours for one weekday (0 = Monday) in the facility's own time zone."""

    __tablename__ = "facility_hours"
    __table_args__ = (
        UniqueConstraint("facility_id", "weekday", name="uq_facility_hours_facility_weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("open_minute BETWEEN 0 AND 1425", name="open_range"),
        CheckConstraint("close_minute BETWEEN 15 AND 1440 AND close_minute > open_minute", name="close_after_open"),
        CheckConstraint("open_minute % 15 = 0 AND close_minute % 15 = 0", name="quarter_hour"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    open_minute: Mapped[int] = mapped_column(Integer)
    close_minute: Mapped[int] = mapped_column(Integer)


class Resource(Base):
    """Something that can be booked: a court, field, lane, table, studio, pool…

    A resource may have one level of children (a full court made of two half
    courts). Booking a parent occupies every child; see services/booking.py.
    """

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("facility_id", "name", name="uq_resources_facility_name"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("slot_minutes > 0 AND slot_minutes % 15 = 0", name="slot_quarter_hour"),
        CheckConstraint("hourly_rate_centavos >= 0", name="rate_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    resource_type_id: Mapped[str] = mapped_column(ForeignKey("resource_types.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=60)
    hourly_rate_centavos: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    facility: Mapped[Facility] = relationship(back_populates="resources")
    resource_type: Mapped[ResourceType] = relationship(lazy="joined")
    sports: Mapped[list[Sport]] = relationship(secondary="resource_sports", order_by="Sport.sort_order", lazy="selectin")
    children: Mapped[list["Resource"]] = relationship(lazy="selectin", order_by="Resource.name")


class ResourceSport(Base):
    __tablename__ = "resource_sports"

    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), primary_key=True)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint("price_centavos >= 0", name="price_non_negative"),
        CheckConstraint("party_size > 0", name="party_positive"),
        one_of("kind", RESERVATION_KINDS, "kind"),
        one_of("status", RESERVATION_STATUSES, "status"),
        one_of("payment_status", PAYMENT_STATUSES, "payment_status"),
        Index("ix_reservations_resource_start", "resource_id", "start_at"),
        Index("ix_reservations_facility_start", "facility_id", "start_at"),
        Index("ix_reservations_organizer_start", "organizer_user_id", "start_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"))
    kind: Mapped[str] = mapped_column(String(16), default="booking")
    organizer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    sport_id: Mapped[str | None] = mapped_column(ForeignKey("sports.id"))
    start_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    price_centavos: Mapped[int] = mapped_column(Integer, default=0)
    payment_status: Mapped[str] = mapped_column(String(16), default="pay_at_venue")
    party_size: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(Text, default="")
    # Copied from the facility's rules when the booking is made.
    free_cancel_until: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    late_cancellation: Mapped[bool] = mapped_column(Boolean, default=False)
    series_id: Mapped[str | None] = mapped_column(String(32), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    decided_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    cancel_reason: Mapped[str] = mapped_column(Text, default="")

    resource: Mapped[Resource] = relationship(lazy="joined")
    facility: Mapped[Facility] = relationship(lazy="joined")
    organizer: Mapped[User] = relationship(foreign_keys=[organizer_user_id], lazy="joined")
    sport: Mapped[Sport | None] = relationship(lazy="joined")


class ReservationSlot(Base):
    """One 15-minute quantum of one unit resource, held by an active reservation.

    The primary key is what makes double-booking impossible.
    """

    __tablename__ = "reservation_slots"

    unit_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    slot_start: Mapped[dt.datetime] = mapped_column(UTCDateTime, primary_key=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), index=True)


# --- communities and teams ---------------------------------------------------


class Community(Base):
    __tablename__ = "communities"
    __table_args__ = (one_of("visibility", COMMUNITY_VISIBILITY, "visibility"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    region_code: Mapped[str | None] = mapped_column(ForeignKey("geo_regions.code"))
    province_code: Mapped[str | None] = mapped_column(ForeignKey("geo_provinces.code"))
    city_code: Mapped[str | None] = mapped_column(ForeignKey("geo_cities.code"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    city: Mapped[GeoCity | None] = relationship(lazy="joined")
    region: Mapped[GeoRegion | None] = relationship(lazy="joined")
    sports: Mapped[list[Sport]] = relationship(secondary="community_sports", order_by="Sport.sort_order", lazy="selectin")
    members: Mapped[list["CommunityMember"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    @property
    def region_name(self) -> str:
        return self.region.name if self.region else ""


class CommunitySport(Base):
    __tablename__ = "community_sports"

    community_id: Mapped[str] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), primary_key=True, index=True)


class CommunityMember(Base):
    __tablename__ = "community_members"
    __table_args__ = (one_of("role", COMMUNITY_ROLES, "role"),)

    community_id: Mapped[str] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("name", "sport_id", name="uq_teams_name_sport"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), index=True)
    community_id: Mapped[str | None] = mapped_column(ForeignKey("communities.id", ondelete="SET NULL"), index=True)
    captain_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    city_code: Mapped[str | None] = mapped_column(ForeignKey("geo_cities.code"))
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    sport: Mapped[Sport] = relationship(lazy="joined")
    city: Mapped[GeoCity | None] = relationship(lazy="joined")
    community: Mapped[Community | None] = relationship(lazy="joined")
    captain: Mapped[User] = relationship(lazy="joined")
    members: Mapped[list["TeamMember"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (one_of("role", TEAM_ROLES, "role"),)

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


# --- open-play sessions ------------------------------------------------------


class PlaySession(Base):
    __tablename__ = "play_sessions"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("confirmed_count >= 0 AND confirmed_count <= capacity", name="confirmed_within_capacity"),
        CheckConstraint("min_players >= 1 AND min_players <= capacity", name="min_players_range"),
        CheckConstraint("fee_centavos >= 0", name="fee_non_negative"),
        CheckConstraint("courts_in_play >= 1", name="courts_positive"),
        one_of("kind", SESSION_KINDS, "kind"),
        one_of("status", SESSION_STATUSES, "status"),
        one_of("join_policy", JOIN_POLICIES, "join_policy"),
        one_of("queue_mode", QUEUE_MODES, "queue_mode"),
        one_of("gender_eligibility", GENDER_ELIGIBILITY, "gender_eligibility"),
        Index("ix_play_sessions_discovery", "status", "start_at"),
        Index("ix_play_sessions_location", "region_code", "province_code", "city_code"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="open_play")
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), index=True)
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("reservations.id", ondelete="SET NULL"))
    host_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    community_id: Mapped[str | None] = mapped_column(ForeignKey("communities.id", ondelete="SET NULL"), index=True)
    series_id: Mapped[str | None] = mapped_column(String(32), index=True)

    start_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila")

    capacity: Mapped[int] = mapped_column(Integer)
    min_players: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=0)

    skill_level: Mapped[str] = mapped_column(String(40), default="All levels")
    team_format: Mapped[str] = mapped_column(String(40), default="")
    gender_eligibility: Mapped[str] = mapped_column(String(16), default="open")
    fee_centavos: Mapped[int] = mapped_column(Integer, default=0)
    join_policy: Mapped[str] = mapped_column(String(16), default="open")
    queue_mode: Mapped[str] = mapped_column(String(16), default="none")
    courts_in_play: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")

    # Where to show up. Copied from the facility, or entered by the host for route-based activities.
    venue_name: Mapped[str] = mapped_column(String(160), default="")
    meetup_note: Mapped[str] = mapped_column(Text, default="")
    route_name: Mapped[str] = mapped_column(String(160), default="")
    route_distance_km: Mapped[float | None] = mapped_column(Float)
    region_code: Mapped[str] = mapped_column(ForeignKey("geo_regions.code"))
    province_code: Mapped[str | None] = mapped_column(ForeignKey("geo_provinces.code"))
    city_code: Mapped[str] = mapped_column(ForeignKey("geo_cities.code"))
    barangay_code: Mapped[str | None] = mapped_column(ForeignKey("geo_barangays.code"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    cancel_reason: Mapped[str] = mapped_column(Text, default="")

    sport: Mapped[Sport] = relationship(lazy="joined")
    facility: Mapped[Facility | None] = relationship(lazy="joined")
    host: Mapped[User] = relationship(lazy="joined")
    community: Mapped[Community | None] = relationship(lazy="joined")
    region: Mapped[GeoRegion] = relationship(lazy="joined")
    province: Mapped[GeoProvince | None] = relationship(lazy="joined")
    city: Mapped[GeoCity] = relationship(lazy="joined")
    barangay: Mapped[GeoBarangay | None] = relationship(lazy="joined")
    participants: Mapped[list["SessionParticipant"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="SessionParticipant.joined_at", lazy="selectin"
    )


class SessionParticipant(Base):
    __tablename__ = "session_participants"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_session_participants_session_user"),
        one_of("status", PARTICIPANT_STATUSES, "status"),
        one_of("queue_state", QUEUE_STATES, "queue_state"),
        Index("ix_session_participants_waitlist", "session_id", "status", "joined_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("play_sessions.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    joined_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    checked_in: Mapped[bool] = mapped_column(Boolean, default=False)
    queue_state: Mapped[str] = mapped_column(String(16), default="idle")
    queued_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    games_played: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[PlaySession] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(lazy="joined")


# --- results -----------------------------------------------------------------


class Match(Base):
    """A two-sided result. The score shape is defined by the sport's scoring_config."""

    __tablename__ = "matches"
    __table_args__ = (
        one_of("status", MATCH_STATUSES, "status"),
        CheckConstraint("winner_side IS NULL OR winner_side IN (1, 2)", name="winner_side"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("play_sessions.id", ondelete="SET NULL"), index=True)
    court_label: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    score: Mapped[dict | None] = mapped_column(JSONType)
    winner_side: Mapped[int | None] = mapped_column(Integer)
    is_draw: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    recorded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    sport: Mapped[Sport] = relationship(lazy="joined")
    players: Mapped[list["MatchPlayer"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (CheckConstraint("side IN (1, 2)", name="side"),)

    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    side: Mapped[int] = mapped_column(Integer)
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)

    user: Mapped[User] = relationship(lazy="joined")


class ActivityLog(Base):
    """An individual result: a run, a ride, a bowling game, a round of golf."""

    __tablename__ = "activity_logs"
    __table_args__ = (
        one_of("source", ACTIVITY_SOURCES, "source"),
        Index("ix_activity_logs_user_sport", "user_id", "sport_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("play_sessions.id", ondelete="SET NULL"))
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    source: Mapped[str] = mapped_column(String(24), default="self_reported")
    note: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    sport: Mapped[Sport] = relationship(lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(255), default="")
    read_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
