from fastapi import APIRouter

from ..models import Community
from ..store import COMMUNITIES

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("", response_model=list[Community])
def read_communities():
    return COMMUNITIES
