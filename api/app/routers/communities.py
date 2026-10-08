from fastapi import APIRouter

from ..legacy import COMMUNITIES, Community

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("", response_model=list[Community])
def read_communities():
    return COMMUNITIES
