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
