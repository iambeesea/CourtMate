"""Request and response shapes. JSON is camelCase; Python is snake_case."""

import datetime as dt
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from .models import SESSION_KINDS

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
SessionKind = Literal[SESSION_KINDS]  # type: ignore[valid-type]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# --- sport configuration ------------------------------------------------------


class TeamFormat(ApiModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    players_per_side: int = Field(ge=1, le=50)


class PlayerConfig(ApiModel):
    min_players: int = Field(ge=1, le=1000)
    max_players: int = Field(ge=1, le=1000)
    team_formats: list[TeamFormat] = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max_players < self.min_players:
            raise ValueError("maxPlayers must be at least minPlayers")
        return self


class MatchFormat(ApiModel):
    type: Literal["two_sided", "individual", "class", "group"]
    session_kinds: list[SessionKind] = Field(min_length=1)
    queue_modes: list[Literal["rotation", "winner_stays"]] = []
    skill_levels: list[str] = Field(default_factory=lambda: ["All levels", "Beginner", "Intermediate", "Advanced"], min_length=1)
    uses_routes: bool = False
    kind_labels: dict[str, str] = {}


class PlayerField(ApiModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    label: str = Field(min_length=1, max_length=40)


class ActivityField(ApiModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    label: str = Field(min_length=1, max_length=40)
    unit: str = Field(default="", max_length=16)
    type: Literal["number", "integer"] = "number"
    min: float | None = None
    max: float | None = None
    required: bool = True


class Aggregation(ApiModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    label: str = Field(min_length=1, max_length=40)
    op: Literal["count", "sum", "avg", "max", "min", "pace", "speed"]
    field: str | None = None
    unit: str = Field(default="", max_length=16)
    decimals: int = Field(default=0, ge=0, le=3)

    @model_validator(mode="after")
    def _needs_field(self):
        if self.op in {"sum", "avg", "max", "min"} and not self.field:
            raise ValueError(f"aggregation '{self.key}' needs a field")
        return self


class ScoringConfig(ApiModel):
    kind: Literal["games", "total", "result", "individual", "none"]
    unit: str = Field(default="", max_length=16)
    best_of: int | None = Field(default=None, ge=1, le=9)
    game_label: str = Field(default="", max_length=20)
    allow_draw: bool = False
    player_fields: list[PlayerField] = []
    activity_fields: list[ActivityField] = []
    aggregations: list[Aggregation] = []

    @model_validator(mode="after")
    def _consistent(self):
        known = {field.key for field in self.activity_fields}
        for aggregation in self.aggregations:
            if aggregation.field and aggregation.field not in known:
                raise ValueError(f"aggregation '{aggregation.key}' refers to unknown field '{aggregation.field}'")
        if self.kind == "individual" and not self.activity_fields:
            raise ValueError("individual scoring needs at least one activity field")
        return self


class CategoryOut(ApiModel):
    id: str
    name: str


class SportSummary(ApiModel):
    id: str
    name: str
    icon: str
    category_id: str


class SportOut(SportSummary):
    category: CategoryOut
    description: str
    booking_eligible: bool
    queue_eligible: bool
    player_config: PlayerConfig
    match_format: MatchFormat
    scoring_config: ScoringConfig
    resource_types: list[str]
    is_active: bool


class SportIn(ApiModel):
    id: Slug
    name: str = Field(min_length=2, max_length=80)
    category_id: str
    icon: str = Field(default="", max_length=40)
    description: LongText = ""
    booking_eligible: bool = True
    queue_eligible: bool = False
    player_config: PlayerConfig
    match_format: MatchFormat
    scoring_config: ScoringConfig
    resource_types: list[str] = []
    sort_order: int = 1000


class SportPatch(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    category_id: str | None = None
    icon: str | None = Field(default=None, max_length=40)
    description: LongText | None = None
    booking_eligible: bool | None = None
    queue_eligible: bool | None = None
    player_config: PlayerConfig | None = None
    match_format: MatchFormat | None = None
    scoring_config: ScoringConfig | None = None
    resource_types: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ResourceTypeOut(ApiModel):
    id: str
    name: str


# --- location -----------------------------------------------------------------


class RegionOut(ApiModel):
    code: str
    name: str
    region_name: str
    island_group: str


class ProvinceOut(ApiModel):
    code: str
    name: str
    region_code: str


class CityOut(ApiModel):
    code: str
    name: str
    region_code: str
    province_code: str | None
    is_city: bool


class BarangayOut(ApiModel):
    code: str
    name: str
    city_code: str


class Place(ApiModel):
    code: str
    name: str


class LocationOut(ApiModel):
    region: Place
    province: Place | None
    city: Place
    barangay: Place | None


# --- accounts -----------------------------------------------------------------


class PublicUser(ApiModel):
    id: str
    display_name: str
    initials: str
    avatar_color: str
    is_demo: bool


class SportProfile(ApiModel):
    sport_id: str
    skill_level: str = Field(default="", max_length=40)
    is_primary: bool = False


class Me(PublicUser):
    email: str
    role: str
    bio: str
    city: CityOut | None
    sports: list[SportProfile]
    managed_facility_ids: list[str]
    created_at: dt.datetime


class RegisterIn(ApiModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)


class LoginIn(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class DemoLoginIn(ApiModel):
    persona: Literal["player", "operator", "admin"] = "player"


class TokenOut(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: dt.datetime
    user: Me


class ProfilePatch(ApiModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=500)
    city_code: str | None = None
    sports: list[SportProfile] | None = Field(default=None, max_length=40)


class AppConfig(ApiModel):
    demo_login: bool
    demo_data: bool
    default_timezone: str
    booking_quantum_minutes: int
    version: str


# --- facilities ---------------------------------------------------------------


class HoursOut(ApiModel):
    weekday: int
    open_minute: int
    close_minute: int
    open_label: str
    close_label: str


class BookingRules(ApiModel):
    requires_approval: bool
    min_notice_minutes: int
    max_advance_days: int
    cancellation_window_hours: int
    min_booking_minutes: int
    max_booking_minutes: int


class ResourceOut(ApiModel):
    id: str
    name: str
    resource_type: ResourceTypeOut
    parent_id: str | None
    child_ids: list[str]
    description: str
    capacity: int
    slot_minutes: int
    hourly_rate_centavos: int
    is_active: bool
    sport_ids: list[str]


class Photo(ApiModel):
    url: str = Field(max_length=500, pattern=r"^https://")
    caption: str = Field(default="", max_length=120)


class FacilitySummary(ApiModel):
    id: str
    name: str
    slug: str
    description: str
    address_line: str
    location: LocationOut
    latitude: float | None
    longitude: float | None
    timezone: str
    amenities: list[str]
    photos: list[Photo]
    sports: list[SportSummary]
    resource_count: int
    from_rate_centavos: int | None
    is_demo: bool
    verification_status: str
    distance_km: float | None = None


class FacilityDetail(FacilitySummary):
    hours: list[HoursOut]
    resources: list[ResourceOut]
    booking_rules: BookingRules


class SlotOut(ApiModel):
    start_at: dt.datetime
    end_at: dt.datetime
    status: Literal["available", "booked", "blocked", "past", "closed"]
    price_centavos: int


class ResourceAvailability(ApiModel):
    resource: ResourceOut
    slots: list[SlotOut]


class FacilityAvailability(ApiModel):
    facility_id: str
    date: dt.date
    timezone: str
    is_open: bool
    open_minute: int | None
    close_minute: int | None
    resources: list[ResourceAvailability]


# --- reservations -------------------------------------------------------------


class ReservationIn(ApiModel):
    resource_id: str
    start_at: AwareDatetime
    end_at: AwareDatetime
    sport_id: str | None = None
    party_size: int = Field(default=1, ge=1, le=1000)
    note: str = Field(default="", max_length=500)
    # Total number of weekly occurrences, including the first.
    repeat_weeks: int = Field(default=1, ge=1, le=12)


class CancelIn(ApiModel):
    reason: str = Field(default="", max_length=300)


class ReservationResource(ApiModel):
    id: str
    name: str
    resource_type: ResourceTypeOut


class ReservationFacility(ApiModel):
    id: str
    name: str
    city_name: str
    address_line: str
    timezone: str
    is_demo: bool


class ReservationOut(ApiModel):
    id: str
    kind: str
    # `completed` is reported for confirmed reservations whose end time has passed.
    status: Literal["pending", "confirmed", "rejected", "cancelled", "completed"]
    resource: ReservationResource
    facility: ReservationFacility
    sport: SportSummary | None
    organizer: PublicUser
    start_at: dt.datetime
    end_at: dt.datetime
    price_centavos: int
    payment_status: str
    party_size: int
    note: str
    free_cancel_until: dt.datetime | None
    late_cancellation: bool
    series_id: str | None
    created_at: dt.datetime
    cancelled_at: dt.datetime | None
    cancel_reason: str
    can_cancel: bool
