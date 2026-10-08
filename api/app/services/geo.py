import math

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import GeoBarangay, GeoCity

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) that contains the search circle."""
    d_lat = math.degrees(radius_km / EARTH_RADIUS_KM)
    d_lng = math.degrees(radius_km / (EARTH_RADIUS_KM * max(math.cos(math.radians(lat)), 0.01)))
    return lat - d_lat, lat + d_lat, lng - d_lng, lng + d_lng


def resolve_place(db: Session, city_code: str, barangay_code: str | None) -> tuple[GeoCity, GeoBarangay | None]:
    """Look up a city and (optionally) one of its barangays, rejecting mismatches."""
    city = db.get(GeoCity, city_code)
    if city is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown city or municipality code.")
    barangay = None
    if barangay_code:
        barangay = db.get(GeoBarangay, barangay_code)
        if barangay is None or barangay.city_code != city.code:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That barangay is not in the selected city or municipality.")
    return city, barangay
