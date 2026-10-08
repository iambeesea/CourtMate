from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..models import GeoBarangay, GeoCity, GeoProvince, GeoRegion

router = APIRouter(prefix="/geo", tags=["location"])

# PSGC reference data only changes when the seed files are rebuilt.
CACHE = "public, max-age=86400"


@router.get("/regions", response_model=list[schemas.RegionOut])
def read_regions(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = CACHE
    return db.scalars(select(GeoRegion).order_by(GeoRegion.code)).all()


@router.get("/provinces", response_model=list[schemas.ProvinceOut])
def read_provinces(response: Response, region_code: str | None = Query(default=None, alias="regionCode"), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = CACHE
    query = select(GeoProvince).order_by(GeoProvince.name)
    if region_code:
        query = query.where(GeoProvince.region_code == region_code)
    return db.scalars(query).all()


@router.get("/cities", response_model=list[schemas.CityOut])
def read_cities(
    response: Response,
    region_code: str | None = Query(default=None, alias="regionCode"),
    province_code: str | None = Query(default=None, alias="provinceCode"),
    q: str | None = Query(default=None, min_length=2, max_length=60, description="Name contains"),
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """Cities and municipalities. With only `regionCode`, returns every one in the region, including those with no province."""
    if not (region_code or province_code or q):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide regionCode, provinceCode or q.")
    response.headers["Cache-Control"] = CACHE
    query = select(GeoCity).order_by(GeoCity.name).limit(limit)
    if region_code:
        query = query.where(GeoCity.region_code == region_code)
    if province_code:
        query = query.where(GeoCity.province_code == province_code)
    if q:
        query = query.where(GeoCity.name.ilike(f"%{q.strip()}%"))
    return db.scalars(query).all()


@router.get("/barangays", response_model=list[schemas.BarangayOut])
def read_barangays(response: Response, city_code: str = Query(alias="cityCode"), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = CACHE
    return db.scalars(select(GeoBarangay).where(GeoBarangay.city_code == city_code).order_by(GeoBarangay.name)).all()
