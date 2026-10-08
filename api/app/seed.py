"""Reference data and clearly labelled demonstration data.

Reference data (sport catalog, resource types, PSGC locations) is inserted when
missing and never overwritten. Demo data is optional (`SEED_DEMO_DATA`) and every
demo row carries `is_demo=True`; nothing here describes a real venue.
"""

import csv
import datetime as dt
import gzip
import io
import re
from pathlib import Path

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from . import schemas
from .models import (
    Facility,
    FacilityHours,
    FacilityStaff,
    GeoBarangay,
    GeoCity,
    GeoProvince,
    GeoRegion,
    PlaySession,
    Resource,
    ResourceType,
    Sport,
    SportCategory,
    User,
    UserSport,
)
from .services import booking
from .services import sessions as sessions_service
from .sports_catalog import CATEGORIES, RESOURCE_TYPES, SPORTS
from .timeutil import at_local_minute, utcnow, zone

PSGC_DIR = Path(__file__).parent / "data" / "psgc"
DEMO_NOTE = "Demonstration venue. This is not a real facility; its prices, hours and availability are sample data."
DEMO_PLAYER_EMAIL = "demo.player@courtmate.demo"
DEMO_OPERATOR_EMAIL = "demo.operator@courtmate.demo"
DEMO_ADMIN_EMAIL = "demo.admin@courtmate.demo"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


# --- reference data -----------------------------------------------------------


def _read_csv(name: str) -> list[dict]:
    path = PSGC_DIR / name
    if name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def load_psgc(db: Session, *, barangay_cities: set[str] | None = None) -> None:
    """Load PSGC locations if the tables are empty.

    `barangay_cities` limits barangays to the given cities; tests use it to stay fast.
    """
    if db.scalar(select(func.count()).select_from(GeoRegion)):
        return
    db.execute(insert(GeoRegion), _read_csv("regions.csv"))
    db.execute(insert(GeoProvince), _read_csv("provinces.csv"))
    db.execute(
        insert(GeoCity),
        [{**row, "province_code": row["province_code"] or None, "is_city": row["is_city"] == "1"} for row in _read_csv("cities.csv")],
    )
    barangays = _read_csv("barangays.csv.gz")
    if barangay_cities is not None:
        barangays = [row for row in barangays if row["city_code"] in barangay_cities]
    for start in range(0, len(barangays), 5000):
        db.execute(insert(GeoBarangay), barangays[start : start + 5000])


def seed_reference(db: Session, *, barangay_cities: set[str] | None = None) -> None:
    existing = set(db.scalars(select(SportCategory.id)).all())
    db.add_all(SportCategory(id=key, name=name, sort_order=index) for index, (key, name) in enumerate(CATEGORIES) if key not in existing)

    existing = set(db.scalars(select(ResourceType.id)).all())
    db.add_all(ResourceType(id=key, name=name, sort_order=index) for index, (key, name) in enumerate(RESOURCE_TYPES) if key not in existing)
    db.flush()

    existing = set(db.scalars(select(Sport.id)).all())
    db.add_all(Sport(**definition, sort_order=index * 10) for index, definition in enumerate(SPORTS) if definition["id"] not in existing)

    load_psgc(db, barangay_cities=barangay_cities)
    db.commit()


# --- demonstration data -------------------------------------------------------

DEMO_PLAYERS = [
    ("Player 01", "#f97068"),
    ("Player 02", "#7f56d9"),
    ("Player 03", "#2e90fa"),
    ("Player 04", "#f79009"),
    ("Player 05", "#12b76a"),
    ("Player 06", "#ee46bc"),
    ("Player 07", "#6172f3"),
    ("Player 08", "#f63d68"),
    ("Player 09", "#15b79e"),
]

DAILY = list(range(7))


def _res(name, kind, sports, capacity, slot, rate_pesos, children=()):
    return {
        "name": name,
        "type": kind,
        "sports": sports,
        "capacity": capacity,
        "slot": slot,
        "rate": rate_pesos * 100,
        "children": list(children),
    }


def _numbered(prefix, count, kind, sports, capacity, slot, rate_pesos):
    return [_res(f"{prefix} {number}", kind, sports, capacity, slot, rate_pesos) for number in range(1, count + 1)]


# Coordinates are approximate city centres, used only to demonstrate map and distance search.
DEMO_FACILITIES = [
    {
        "name": "Demo Rally Center",
        "city": "137404000",
        "barangay": "137404011",
        "lat": 14.6760,
        "lng": 121.0437,
        "hours": (360, 1320),
        "amenities": ["Parking", "Showers", "Equipment rental", "Air-conditioned"],
        "rules": {"min_booking_minutes": 30, "max_booking_minutes": 180},
        "resources": [
            *_numbered("Pickleball Court", 4, "court", ["pickleball"], 4, 60, 400),
            *_numbered("Badminton Court", 4, "court", ["badminton"], 4, 60, 300),
            *_numbered("Table", 2, "table", ["table_tennis"], 4, 30, 150),
        ],
    },
    {
        "name": "Demo Hoops and Spikes Arena",
        "city": "031410000",
        "barangay": "031410012",
        "lat": 14.8433,
        "lng": 120.8114,
        "hours": (360, 1320),
        "amenities": ["Parking", "Scoreboard", "Bleachers", "Drinking water"],
        "rules": {"requires_approval": True, "max_booking_minutes": 180},
        "resources": [
            _res(
                "Main Court",
                "court",
                ["basketball", "volleyball"],
                30,
                60,
                1200,
                children=[
                    _res("Half Court A", "half_court", ["basketball"], 15, 60, 650),
                    _res("Half Court B", "half_court", ["basketball"], 15, 60, 650),
                ],
            ),
            _res("Volleyball Court", "court", ["volleyball"], 24, 60, 800),
        ],
    },
    {
        "name": "Demo Strike and Cue Lounge",
        "city": "035416000",
        "barangay": None,
        "lat": 15.0286,
        "lng": 120.6898,
        "hours": (600, 1440),
        "amenities": ["Parking", "Food and drinks", "Shoe rental"],
        "rules": {"min_booking_minutes": 30, "max_booking_minutes": 180, "cancellation_window_hours": 6},
        "resources": [
            *_numbered("Lane", 4, "lane", ["bowling"], 6, 60, 500),
            *_numbered("Pool Table", 3, "table", ["billiards"], 4, 60, 200),
            *_numbered("Dart Station", 2, "station", ["darts"], 4, 30, 120),
            _res("Chess Table", "table", ["chess"], 2, 60, 0),
        ],
    },
    {
        "name": "Demo Aquatic and Fitness Club",
        "city": "043428000",
        "barangay": None,
        "lat": 14.3122,
        "lng": 121.1114,
        "hours": (330, 1260),
        "amenities": ["Lockers", "Showers", "Lifeguard on duty", "Parking"],
        "rules": {"min_booking_minutes": 30, "max_booking_minutes": 120},
        "resources": [
            _res(
                "25 m Pool",
                "pool",
                ["swimming"],
                40,
                60,
                2400,
                children=_numbered("Pool Lane", 4, "pool_lane", ["swimming"], 6, 30, 300),
            ),
            _res("Studio A", "studio", ["yoga", "dance_fitness"], 25, 60, 900),
            _res("Mat Room", "training_area", ["martial_arts", "bjj", "taekwondo", "boxing", "muay_thai", "calisthenics"], 20, 60, 700),
            _res("Bouldering Wall", "climbing_wall", ["climbing"], 15, 60, 1000),
        ],
    },
    {
        "name": "Demo Football and Tennis Park",
        "city": "072217000",
        "barangay": "072217041",
        "lat": 10.3157,
        "lng": 123.8854,
        "hours": (360, 1320),
        "amenities": ["Floodlights", "Parking", "Changing rooms"],
        "rules": {"max_booking_minutes": 180},
        "resources": [
            _res(
                "Main Pitch",
                "field",
                ["football"],
                44,
                60,
                2500,
                children=[
                    _res("Half Pitch North", "half_field", ["football"], 22, 60, 1400),
                    _res("Half Pitch South", "half_field", ["football"], 22, 60, 1400),
                ],
            ),
            *_numbered("Tennis Court", 2, "court", ["tennis"], 4, 60, 450),
            _res("Diamond", "field", ["baseball", "softball"], 40, 120, 1500),
            _res("Sand Court", "court", ["beach_volleyball"], 8, 60, 500),
        ],
    },
    {
        "name": "Demo Greens Golf Course",
        "city": "112402000",
        "barangay": None,
        "lat": 7.1907,
        "lng": 125.4553,
        "hours": (330, 1020),
        "amenities": ["Clubhouse", "Cart rental", "Parking"],
        "rules": {"min_booking_minutes": 15, "max_booking_minutes": 15, "min_notice_minutes": 120, "cancellation_window_hours": 48},
        "resources": [_res("First Tee", "tee", ["golf"], 4, 15, 6000)],
    },
]

DEMO_CITY_CODES = {item["city"] for item in DEMO_FACILITIES}


def _demo_user(db: Session, email: str, name: str, color: str, *, role: str = "player", city_code: str | None = None) -> User:
    user = User(email=email, password_hash=None, display_name=name, role=role, avatar_color=color, is_demo=True, city_code=city_code)
    db.add(user)
    return user


def _add_resource(db: Session, facility: Facility, definition: dict, order: int, parent: Resource | None = None) -> Resource:
    resource = Resource(
        facility_id=facility.id,
        parent_id=parent.id if parent else None,
        name=definition["name"],
        resource_type_id=definition["type"],
        capacity=definition["capacity"],
        slot_minutes=definition["slot"],
        hourly_rate_centavos=definition["rate"],
        sort_order=order,
    )
    resource.sports = [db.get(Sport, sport_id) for sport_id in definition["sports"]]
    db.add(resource)
    db.flush()
    for index, child in enumerate(definition["children"]):
        _add_resource(db, facility, child, order * 10 + index + 1, resource)
    return resource


def _demo_facility(db: Session, definition: dict, operator: User) -> Facility:
    city = db.get(GeoCity, definition["city"])
    barangay = db.get(GeoBarangay, definition["barangay"]) if definition["barangay"] else None
    open_minute, close_minute = definition["hours"]
    facility = Facility(
        name=definition["name"],
        slug=slugify(definition["name"]),
        description=DEMO_NOTE,
        address_line=f"Sample address, {city.name}",
        region_code=city.region_code,
        province_code=city.province_code,
        city_code=city.code,
        barangay_code=barangay.code if barangay else None,
        latitude=definition["lat"],
        longitude=definition["lng"],
        amenities=definition["amenities"],
        verification_status="verified",
        is_demo=True,
        owner_user_id=operator.id,
        contact_name="Demo Operator",
        contact_email=DEMO_OPERATOR_EMAIL,
        **definition["rules"],
    )
    db.add(facility)
    db.flush()
    db.add(FacilityStaff(facility_id=facility.id, user_id=operator.id, role="owner"))
    db.add_all(FacilityHours(facility_id=facility.id, weekday=day, open_minute=open_minute, close_minute=close_minute) for day in DAILY)
    sport_ids: list[str] = []
    for index, resource in enumerate(definition["resources"]):
        _add_resource(db, facility, resource, index)
        for sport_id in [*resource["sports"], *(sport for child in resource["children"] for sport in child["sports"])]:
            if sport_id not in sport_ids:
                sport_ids.append(sport_id)
    facility.sports = [db.get(Sport, sport_id) for sport_id in sport_ids]
    db.flush()
    db.refresh(facility)
    return facility


def _demo_bookings(db: Session, facility: Facility, players: list[User], operator: User, now: dt.datetime) -> None:
    """A few bookings and one maintenance block so the demo calendar is not empty."""
    tz = zone(facility.timezone)
    tomorrow = now.astimezone(tz).date() + dt.timedelta(days=1)
    by_name = {resource.name: resource for resource in facility.resources}

    def hold(resource_name: str, start_minute: int, minutes: int, player: User, sport_id: str) -> None:
        start = at_local_minute(tomorrow, start_minute, tz)
        booking.create_booking(
            db,
            facility=facility,
            resource=by_name[resource_name],
            organizer=player,
            start_at=start,
            end_at=start + dt.timedelta(minutes=minutes),
            sport_id=sport_id,
            party_size=4,
            now=now,
        )

    hold("Pickleball Court 1", 18 * 60, 120, players[0], "pickleball")
    hold("Pickleball Court 2", 19 * 60, 60, players[1], "pickleball")
    hold("Badminton Court 1", 18 * 60, 120, players[4], "badminton")
    start = at_local_minute(tomorrow, 8 * 60, tz)
    booking.create_block(
        db,
        facility=facility,
        resource=by_name["Badminton Court 4"],
        staff=operator,
        start_at=start,
        end_at=start + dt.timedelta(hours=4),
        reason="Demo: floor maintenance",
    )


def seed_demo(db: Session, *, now: dt.datetime | None = None) -> bool:
    """Insert demo data once. Returns True when it inserted anything."""
    if db.scalar(select(User.id).where(User.email == DEMO_PLAYER_EMAIL)):
        return False
    now = now or utcnow()

    player = _demo_user(db, DEMO_PLAYER_EMAIL, "Demo Player", "#f8c8ad", city_code="137404000")
    operator = _demo_user(db, DEMO_OPERATOR_EMAIL, "Demo Operator", "#1f3b73")
    _demo_user(db, DEMO_ADMIN_EMAIL, "Demo Admin", "#12b76a", role="admin")
    players = [
        _demo_user(db, f"demo.p{index:02d}@courtmate.demo", name, color, city_code="137404000")
        for index, (name, color) in enumerate(DEMO_PLAYERS, start=1)
    ]
    db.flush()
    player.bio = "Always game for a good rally. Building community one court at a time."
    db.add_all(
        [
            UserSport(user_id=player.id, sport_id="pickleball", skill_level="3.0", is_primary=True),
            UserSport(user_id=player.id, sport_id="badminton", skill_level="Intermediate"),
        ]
    )

    facilities = [_demo_facility(db, definition, operator) for definition in DEMO_FACILITIES]
    _demo_bookings(db, facilities[0], players, operator, now)
    seed_demo_sessions(db, now=now)
    db.commit()
    return True


# Each tuple: title, sport, kind, facility name (or None), day offset, start minute, minutes, capacity, players joined, extras.
DEMO_SESSIONS = [
    (
        "Saturday Sunrise Rally",
        "pickleball",
        "open_play",
        "Demo Rally Center",
        1,
        7 * 60,
        120,
        12,
        7,
        {"skill_level": "3.0", "team_format": "doubles", "fee": 220, "queue_mode": "rotation", "courts": 2},
    ),
    (
        "After Work Smash",
        "badminton",
        "open_play",
        "Demo Rally Center",
        2,
        18 * 60 + 30,
        150,
        8,
        9,
        {"skill_level": "Intermediate", "team_format": "doubles", "fee": 180, "queue_mode": "rotation", "courts": 2},
    ),
    (
        "Midweek Dink and Drink",
        "pickleball",
        "open_play",
        "Demo Rally Center",
        4,
        17 * 60 + 30,
        120,
        12,
        3,
        {"team_format": "doubles", "fee": 250},
    ),
    (
        "Saturday Hoops Run",
        "basketball",
        "pickup_game",
        "Demo Hoops and Spikes Arena",
        3,
        18 * 60,
        120,
        15,
        6,
        {"team_format": "5v5", "fee": 100, "queue_mode": "winner_stays", "join_policy": "approval"},
    ),
    (
        "Volleyball Night",
        "volleyball",
        "pickup_game",
        "Demo Hoops and Spikes Arena",
        5,
        19 * 60,
        120,
        18,
        5,
        {"team_format": "6v6", "fee": 80},
    ),
    ("Friday Bowling Social", "bowling", "open_play", "Demo Strike and Cue Lounge", 2, 19 * 60, 120, 12, 4, {"fee": 350}),
    (
        "Beginner Yoga Flow",
        "yoga",
        "class",
        "Demo Aquatic and Fitness Club",
        1,
        6 * 60 + 30,
        60,
        20,
        5,
        {"skill_level": "Beginner", "fee": 250},
    ),
    ("Open Mat", "bjj", "sparring", "Demo Aquatic and Fitness Club", 3, 19 * 60, 90, 16, 4, {"fee": 200}),
    ("Lap Swim Squad", "swimming", "open_play", "Demo Aquatic and Fitness Club", 2, 6 * 60, 60, 12, 3, {"fee": 150}),
    (
        "Seven-a-side Kickabout",
        "football",
        "pickup_game",
        "Demo Football and Tennis Park",
        4,
        18 * 60,
        90,
        16,
        6,
        {"team_format": "7v7", "fee": 120},
    ),
    ("Morning Tee Time", "golf", "tee_time", "Demo Greens Golf Course", 6, 6 * 60, 240, 4, 2, {"fee": 1500}),
    (
        "Sunday Long Run",
        "running",
        "group_activity",
        None,
        3,
        5 * 60 + 30,
        90,
        40,
        6,
        {
            "city": "137404000",
            "venue": "Demo meet-up point, Quezon City",
            "route": "Demo 10 km loop",
            "km": 10.0,
            "lat": 14.6510,
            "lng": 121.0493,
        },
    ),
    (
        "Weekend Gravel Ride",
        "cycling",
        "group_activity",
        None,
        5,
        5 * 60,
        180,
        25,
        4,
        {
            "city": "043428000",
            "venue": "Demo meet-up point, Santa Rosa",
            "route": "Demo 45 km out-and-back",
            "km": 45.0,
            "lat": 14.3122,
            "lng": 121.1114,
        },
    ),
]


def _demo_session(
    db: Session, host: User, players: list[User], facilities: dict[str, Facility], row: tuple, now: dt.datetime
) -> PlaySession:
    title, sport_id, kind, facility_name, day_offset, start_minute, minutes, capacity, joined, extra = row
    facility = facilities.get(facility_name) if facility_name else None
    tz = zone(facility.timezone if facility else None)
    start = at_local_minute(now.astimezone(tz).date() + dt.timedelta(days=day_offset), start_minute, tz)
    payload = schemas.SessionIn(
        title=title,
        description="Demonstration session with sample players.",
        sport_id=sport_id,
        kind=kind,
        start_at=start,
        end_at=start + dt.timedelta(minutes=minutes),
        capacity=capacity,
        skill_level=extra.get("skill_level", "All levels"),
        team_format=extra.get("team_format", ""),
        fee_centavos=extra.get("fee", 0) * 100,
        join_policy=extra.get("join_policy", "open"),
        queue_mode=extra.get("queue_mode", "none"),
        courts_in_play=extra.get("courts", 1),
        facility_id=facility.id if facility else None,
        city_code=extra.get("city"),
        venue_name=extra.get("venue", ""),
        route_name=extra.get("route", ""),
        route_distance_km=extra.get("km"),
        latitude=extra.get("lat"),
        longitude=extra.get("lng"),
    )
    [session] = sessions_service.create(db, host, payload, now=now)
    session.is_demo = True
    session.join_policy = "open"  # let the sample players in, then restore the real policy below
    for offset, player in enumerate(player for player in players if player.id != host.id):
        if offset >= joined - 1:
            break
        sessions_service.join(db, session, player, now=now - dt.timedelta(hours=1) + dt.timedelta(seconds=offset))
    session.join_policy = extra.get("join_policy", "open")
    return session


def _demo_live_session(db: Session, host: User, players: list[User], facility: Facility, me: User, now: dt.datetime) -> None:
    """A session that is already under way, so the Play tab has a working queue to show."""
    start = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    payload = schemas.SessionIn(
        title="Demo Live Queue",
        description="A demonstration session in progress. Check in to join the queue.",
        sport_id="badminton",
        kind="open_play",
        start_at=start,
        end_at=start + dt.timedelta(hours=3),
        capacity=12,
        skill_level="All levels",
        team_format="doubles",
        queue_mode="rotation",
        courts_in_play=2,
        facility_id=facility.id,
    )
    [session] = sessions_service.create(db, host, payload, now=now)
    session.is_demo = True
    for offset, player in enumerate([*[item for item in players if item.id != host.id][:6], me]):
        sessions_service.join(db, session, player, now=now - dt.timedelta(hours=1) + dt.timedelta(seconds=offset))
    sessions_service.start_session(db, session, now=now)
    db.flush()
    db.refresh(session)
    for offset, participant in enumerate(item for item in session.participants if item.user_id != me.id):
        sessions_service.check_in(db, session, participant, now=now - dt.timedelta(minutes=30) + dt.timedelta(seconds=offset))
    db.flush()
    sessions_service.call_next(db, session, host, now=now)


def seed_demo_sessions(db: Session, *, now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    me = db.scalar(select(User).where(User.email == DEMO_PLAYER_EMAIL))
    players = list(db.scalars(select(User).where(User.email.like("demo.p0%@courtmate.demo")).order_by(User.email)).all())
    facilities = {facility.name: facility for facility in db.scalars(select(Facility).where(Facility.is_demo.is_(True))).all()}
    for index, row in enumerate(DEMO_SESSIONS):
        _demo_session(db, players[index % len(players)], players, facilities, row, now)
    _demo_live_session(db, players[1], players, facilities["Demo Rally Center"], me, now)
    db.flush()


def refresh_demo_sessions(db: Session, *, now: dt.datetime | None = None) -> bool:
    """On a database that outlives its demo sessions, add a fresh set so the demo never looks stale."""
    now = now or utcnow()
    if not db.scalar(select(User.id).where(User.email == DEMO_PLAYER_EMAIL)):
        return False
    upcoming = db.scalar(
        select(func.count())
        .select_from(PlaySession)
        .where(PlaySession.is_demo.is_(True), PlaySession.status == "scheduled", PlaySession.end_at > now)
    )
    if upcoming:
        return False
    # Close out a demo session left "live" from an earlier run.
    for stale in db.scalars(select(PlaySession).where(PlaySession.is_demo.is_(True), PlaySession.status == "live")).all():
        sessions_service.complete_session(db, stale, now=now)
    seed_demo_sessions(db, now=now)
    db.commit()
    return True
