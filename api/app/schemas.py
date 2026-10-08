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


# --- open-play sessions -------------------------------------------------------

MAX_FEE_CENTAVOS = 10_000_000


class SessionIn(ApiModel):
    title: str = Field(min_length=3, max_length=120)
    description: LongText = ""
    sport_id: str
    kind: SessionKind = "open_play"
    start_at: AwareDatetime
    end_at: AwareDatetime
    capacity: int = Field(ge=1, le=1000)
    min_players: int = Field(default=1, ge=1, le=1000)
    skill_level: str = Field(default="All levels", max_length=40)
    team_format: str = Field(default="", max_length=40)
    gender_eligibility: Literal["open", "women", "men", "mixed"] = "open"
    fee_centavos: int = Field(default=0, ge=0, le=MAX_FEE_CENTAVOS)
    join_policy: Literal["open", "approval"] = "open"
    queue_mode: Literal["none", "rotation", "winner_stays"] = "none"
    courts_in_play: int = Field(default=1, ge=1, le=30)
    host_plays: bool = True

    # Where: a listed facility, or a place described by the host.
    facility_id: str | None = None
    resource_id: str | None = Field(default=None, description="Also reserve this resource for the session's time.")
    city_code: str | None = None
    barangay_code: str | None = None
    venue_name: str = Field(default="", max_length=160)
    meetup_note: str = Field(default="", max_length=500)
    route_name: str = Field(default="", max_length=160)
    route_distance_km: float | None = Field(default=None, gt=0, le=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    community_id: str | None = None
    repeat_weeks: int = Field(default=1, ge=1, le=12)

    @model_validator(mode="after")
    def _coherent(self):
        if self.min_players > self.capacity:
            raise ValueError("minPlayers cannot be more than capacity")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("provide both latitude and longitude, or neither")
        if self.resource_id and not self.facility_id:
            raise ValueError("resourceId needs facilityId")
        return self


class SessionPatch(ApiModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: LongText | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=1000)
    min_players: int | None = Field(default=None, ge=1, le=1000)
    skill_level: str | None = Field(default=None, max_length=40)
    fee_centavos: int | None = Field(default=None, ge=0, le=MAX_FEE_CENTAVOS)
    join_policy: Literal["open", "approval"] | None = None
    queue_mode: Literal["none", "rotation", "winner_stays"] | None = None
    courts_in_play: int | None = Field(default=None, ge=1, le=30)
    meetup_note: str | None = Field(default=None, max_length=500)


class JoinIn(ApiModel):
    team_id: str | None = None


class SessionFacility(ApiModel):
    id: str
    name: str
    slug: str
    is_demo: bool


class SessionCommunity(ApiModel):
    id: str
    name: str


class ViewerState(ApiModel):
    status: str | None
    is_host: bool
    waitlist_position: int | None
    checked_in: bool
    queue_state: str | None


class SessionOut(ApiModel):
    id: str
    title: str
    description: str
    kind: str
    kind_label: str
    sport: SportSummary
    facility: SessionFacility | None
    venue_name: str
    meetup_note: str
    route_name: str
    route_distance_km: float | None
    location: LocationOut
    latitude: float | None
    longitude: float | None
    distance_km: float | None = None
    start_at: dt.datetime
    end_at: dt.datetime
    timezone: str
    capacity: int
    min_players: int
    joined: int
    waitlist: int
    pending: int
    spots_left: int
    skill_level: str
    team_format: str
    team_format_label: str
    gender_eligibility: str
    fee_centavos: int
    join_policy: str
    queue_mode: str
    courts_in_play: int
    status: str
    cancel_reason: str
    host: PublicUser
    community: SessionCommunity | None
    series_id: str | None
    has_venue_booking: bool
    is_demo: bool
    players: list[PublicUser]
    viewer: ViewerState


class ParticipantOut(ApiModel):
    id: str
    user: PublicUser
    status: str
    joined_at: dt.datetime
    checked_in: bool
    queue_state: str
    games_played: int
    waitlist_position: int | None = None


class SessionDetail(SessionOut):
    participants: list[ParticipantOut]


# --- queues and matches -------------------------------------------------------


class QueueStateIn(ApiModel):
    state: Literal["waiting", "idle"]


class NextMatchIn(ApiModel):
    court: int | None = Field(default=None, ge=1, le=30)


class MatchResultIn(ApiModel):
    """Exactly one of `games`, `totals` or `winner`, matching the sport's scoring kind."""

    games: list[tuple[int, int]] | None = Field(default=None, max_length=9)
    totals: tuple[int, int] | None = None
    winner: Literal[1, 2] | None = None
    draw: bool = False
    player_stats: dict[str, dict[str, int]] = {}


class MatchPlayerOut(ApiModel):
    user: PublicUser
    side: int
    stats: dict[str, int]


class MatchOut(ApiModel):
    id: str
    sport: SportSummary
    session_id: str | None
    court_label: str
    status: str
    score: dict | None
    winner_side: int | None
    is_draw: bool
    started_at: dt.datetime
    completed_at: dt.datetime | None
    players: list[MatchPlayerOut]
    is_demo: bool


class CourtOut(ApiModel):
    number: int
    label: str
    match: MatchOut | None


class QueueOut(ApiModel):
    session_id: str
    mode: str
    status: str
    players_per_match: int
    courts: list[CourtOut]
    waiting: list[ParticipantOut]
    resting: list[ParticipantOut]
    not_checked_in: list[ParticipantOut]
    can_manage: bool


# --- communities and teams ----------------------------------------------------


class MemberOut(ApiModel):
    user: PublicUser
    role: str
    joined_at: dt.datetime


class CommunityIn(ApiModel):
    name: str = Field(min_length=3, max_length=120)
    description: LongText = ""
    city_code: str | None = None
    sport_ids: list[str] = Field(min_length=1, max_length=30)
    visibility: Literal["public", "private"] = "public"


class CommunityPatch(ApiModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: LongText | None = None
    city_code: str | None = None
    sport_ids: list[str] | None = Field(default=None, min_length=1, max_length=30)


class CommunityOut(ApiModel):
    id: str
    name: str
    slug: str
    description: str
    city: Place | None
    region: Place | None
    sports: list[SportSummary]
    member_count: int
    visibility: str
    is_demo: bool
    viewer_role: str | None


class TeamIn(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    sport_id: str
    community_id: str | None = None
    city_code: str | None = None
    description: LongText = ""


class TeamOut(ApiModel):
    id: str
    name: str
    sport: SportSummary
    community: SessionCommunity | None
    city: Place | None
    description: str
    member_count: int
    captain: PublicUser
    is_demo: bool
    viewer_role: str | None


class TeamDetail(TeamOut):
    members: list[MemberOut]


class CommunityDetail(CommunityOut):
    members: list[MemberOut]
    teams: list[TeamOut]


# --- player records -----------------------------------------------------------


class StatValue(ApiModel):
    key: str
    label: str
    value: float
    display: str
    unit: str = ""
    note: str = ""


class MonthCount(ApiModel):
    month: str
    label: str
    count: int


class PartnerStat(ApiModel):
    user: PublicUser
    matches: int
    wins: int


class StatsOut(ApiModel):
    sport: SportSummary
    # How this sport keeps records: head-to-head results, logged activities, or attendance.
    record_type: Literal["matches", "activities", "attendance"]
    has_data: bool
    summary: list[StatValue]
    recent_form: list[Literal["W", "L", "D"]]
    streak_type: Literal["W", "L", "D"] | None
    streak: int
    best_win_streak: int
    by_month: list[MonthCount]
    partners: list[PartnerStat]
    contains_demo_data: bool


class RecordOverview(ApiModel):
    """Which sports a player has results in, most active first."""

    sport: SportSummary
    record_type: str
    entries: int
    last_played_at: dt.datetime | None


class MyMatchOut(MatchOut):
    result: Literal["W", "L", "D"]
    my_side: int


class ActivityIn(ApiModel):
    sport_id: str
    occurred_at: AwareDatetime
    metrics: dict[str, float] = Field(max_length=12)
    note: str = Field(default="", max_length=300)


class ActivityOut(ApiModel):
    id: str
    sport: SportSummary
    occurred_at: dt.datetime
    metrics: dict[str, float]
    source: str
    note: str
    is_demo: bool


class AchievementOut(ApiModel):
    id: str
    label: str
    description: str


# --- notifications ------------------------------------------------------------


class NotificationOut(ApiModel):
    id: str
    kind: str
    title: str
    body: str
    link: str
    read_at: dt.datetime | None
    created_at: dt.datetime


class NotificationList(ApiModel):
    unread: int
    items: list[NotificationOut]


class MarkReadIn(ApiModel):
    ids: list[str] | None = Field(default=None, max_length=200)
