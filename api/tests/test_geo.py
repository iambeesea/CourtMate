import json

from sqlalchemy import func, select

from app import db as database
from app import seed
from app.db import Base
from app.models import GeoBarangay, GeoCity, GeoProvince, GeoRegion

from .conftest import API

NCR, CENTRAL_LUZON, CALABARZON = "130000000", "030000000", "040000000"
BULACAN, QUEZON_CITY = "031400000", "137404000"


def test_regions(client):
    response = client.get(f"{API}/geo/regions")
    regions = {item["code"]: item for item in response.json()}
    assert len(regions) == 17
    assert regions[NCR]["regionName"] == "National Capital Region"
    assert regions[CENTRAL_LUZON]["name"] == "Central Luzon"
    assert regions[CALABARZON]["name"] == "CALABARZON"
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_provinces_by_region(client):
    names = {item["name"] for item in client.get(f"{API}/geo/provinces", params={"regionCode": CENTRAL_LUZON}).json()}
    assert {"Bulacan", "Pampanga", "Tarlac", "Bataan", "Nueva Ecija", "Zambales", "Aurora"} == names
    assert client.get(f"{API}/geo/provinces", params={"regionCode": NCR}).json() == []


def test_ncr_cities_have_no_province(client):
    cities = client.get(f"{API}/geo/cities", params={"regionCode": NCR}).json()
    assert len(cities) == 17
    assert all(city["provinceCode"] is None for city in cities)
    assert "Quezon City" in {city["name"] for city in cities}


def test_cities_by_province_and_search(client):
    bulacan = client.get(f"{API}/geo/cities", params={"provinceCode": BULACAN}).json()
    assert {"City of Malolos", "City of Meycauayan", "City of San Jose Del Monte"} <= {city["name"] for city in bulacan}
    assert all(city["regionCode"] == CENTRAL_LUZON for city in bulacan)
    found = client.get(f"{API}/geo/cities", params={"q": "malolos"}).json()
    assert [city["code"] for city in found] == ["031410000"]


def test_cities_need_a_filter(client):
    assert client.get(f"{API}/geo/cities").status_code == 422


def test_barangays_by_city(client):
    barangays = client.get(f"{API}/geo/barangays", params={"cityCode": QUEZON_CITY}).json()
    assert len(barangays) == 142
    assert "Bagumbayan" in {item["name"] for item in barangays}
    assert barangays == sorted(barangays, key=lambda item: item["name"])


def test_full_psgc_dataset_loads_with_intact_references(tmp_path):
    """Loads every barangay (the other tests load a subset) and checks counts against the manifest."""
    engine = database.configure(f"sqlite:///{tmp_path / 'psgc.db'}")
    Base.metadata.create_all(engine)
    manifest = json.loads((seed.PSGC_DIR / "manifest.json").read_text())["counts"]
    with database.session_factory()() as session:
        seed.load_psgc(session)
        session.commit()
        count = lambda model: session.scalar(select(func.count()).select_from(model))  # noqa: E731
        assert count(GeoRegion) == manifest["regions"] == 17
        assert count(GeoProvince) == manifest["provinces"] == 81
        assert count(GeoCity) == manifest["citiesMunicipalities"] == 1634
        assert count(GeoBarangay) == manifest["barangays"] == 42046
        orphans = session.scalar(
            select(func.count())
            .select_from(GeoBarangay)
            .outerjoin(GeoCity, GeoCity.code == GeoBarangay.city_code)
            .where(GeoCity.code.is_(None))
        )
        assert orphans == 0
        # Loading twice is a no-op.
        seed.load_psgc(session)
        assert count(GeoRegion) == 17
    engine.dispose()
