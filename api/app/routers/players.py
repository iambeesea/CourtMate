from fastapi import APIRouter

from ..legacy import STATS, PlayerStats

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/me/stats", response_model=PlayerStats)
def read_my_stats():
    return STATS
