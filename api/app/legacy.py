"""Seeded in-memory data behind the original MVP routes.

Kept only until the database-backed sessions, statistics and communities
replace it later on this branch.
"""

from copy import deepcopy
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Player(ApiModel):
    id: str
    name: str
    initials: str
    level: str
    color: str


class Session(ApiModel):
    id: str
    title: str
    sport: Literal["Pickleball", "Badminton"]
    venue: str
    city: str
    date: date
    day_label: str
    time: str
    level: str
    format: str
    price: int
    capacity: int
    joined: int
    waitlist: int
    organizer: str
    accent: Literal["lime", "violet", "orange"]
    players: list[Player]
    is_joined: bool = False


class PlayerStats(ApiModel):
    matches: int
    wins: int
    losses: int
    win_rate: int
    streak: int
    rating: float
    recent_form: list[Literal["W", "L"]]


class Community(ApiModel):
    id: str
    name: str
    city: str
    members: int
    sports: list[str]


SESSIONS = [
    Session(
        id="session-001",
        title="Saturday Sunrise Rally",
        sport="Pickleball",
        venue="Riverside Courts",
        city="Metro Area",
        date="2026-08-30",
        day_label="SUN",
        time="7:00 AM – 9:00 AM",
        level="Beginner friendly",
        format="Open play · Rotating doubles",
        price=220,
        capacity=16,
        joined=13,
        waitlist=0,
        organizer="Rally Community",
        accent="lime",
        players=[
            {"id": "p1", "name": "Player 01", "initials": "P1", "level": "3.0", "color": "#f97068"},
            {"id": "p2", "name": "Player 02", "initials": "P2", "level": "2.5", "color": "#7f56d9"},
            {"id": "p3", "name": "Player 03", "initials": "P3", "level": "3.0", "color": "#2e90fa"},
            {"id": "p4", "name": "Player 04", "initials": "P4", "level": "2.5", "color": "#f79009"},
        ],
    ),
    Session(
        id="session-002",
        title="After Work Smash",
        sport="Badminton",
        venue="Central Badminton Hall",
        city="Metro Area",
        date="2026-08-31",
        day_label="MON",
        time="6:30 PM – 9:00 PM",
        level="Intermediate",
        format="Queue play · Doubles",
        price=180,
        capacity=20,
        joined=18,
        waitlist=3,
        organizer="Shuttle Community",
        accent="violet",
        players=[
            {"id": "p5", "name": "Player 05", "initials": "P5", "level": "B", "color": "#12b76a"},
            {"id": "p6", "name": "Player 06", "initials": "P6", "level": "B+", "color": "#ee46bc"},
            {"id": "p7", "name": "Player 07", "initials": "P7", "level": "B", "color": "#6172f3"},
        ],
    ),
    Session(
        id="session-003",
        title="Midweek Dink & Drink",
        sport="Pickleball",
        venue="Northside Sports Hub",
        city="Metro Area",
        date="2026-09-02",
        day_label="WED",
        time="5:30 PM – 7:30 PM",
        level="All levels",
        format="Social open play",
        price=250,
        capacity=12,
        joined=7,
        waitlist=0,
        organizer="Dink Community",
        accent="lime",
        players=[
            {"id": "p8", "name": "Player 08", "initials": "P8", "level": "3.5", "color": "#f63d68"},
            {"id": "p9", "name": "Player 09", "initials": "P9", "level": "3.0", "color": "#15b79e"},
        ],
    ),
]

STATS = PlayerStats(matches=28, wins=18, losses=10, win_rate=64, streak=4, rating=3.12, recent_form=["W", "W", "L", "W", "W"])
COMMUNITIES = [
    Community(id="community-001", name="Rally Community", city="Metro Area", members=184, sports=["Pickleball"]),
    Community(id="community-002", name="Shuttle Community", city="Metro Area", members=96, sports=["Badminton"]),
    Community(id="community-003", name="Dink Community", city="Metro Area", members=71, sports=["Pickleball"]),
]


def list_sessions() -> list[Session]:
    return deepcopy(SESSIONS)


def get_session(session_id: str) -> Session | None:
    return next((session for session in SESSIONS if session.id == session_id), None)
