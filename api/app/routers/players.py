from fastapi import APIRouter

from ..models import PlayerStats
from ..store import STATS

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/me/stats", response_model=PlayerStats)
def read_my_stats():
    return STATS
