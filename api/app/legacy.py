"""Seeded in-memory data behind the original statistics and communities routes.

Kept only until the database-backed versions replace it in phase 4.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


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


STATS = PlayerStats(matches=28, wins=18, losses=10, win_rate=64, streak=4, rating=3.12, recent_form=["W", "W", "L", "W", "W"])
COMMUNITIES = [
    Community(id="community-001", name="Rally Community", city="Metro Area", members=184, sports=["Pickleball"]),
    Community(id="community-002", name="Shuttle Community", city="Metro Area", members=96, sports=["Badminton"]),
    Community(id="community-003", name="Dink Community", city="Metro Area", members=71, sports=["Pickleball"]),
]
