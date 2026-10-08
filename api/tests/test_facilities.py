import datetime as dt

from app.models import Facility, User

from .conftest import API, MANILA, facility_named

QC = (14.6760, 121.0437)


def names(response):
    return [item["name"] for item in response.json()]


def test_demo_facilities_are_listed_and_labelled(client):
    response = client.get(f"{API}/facilities")
    body = response.json()
    assert response.headers["x-total-count"] == "6"
    assert len(body) == 6
    assert all(item["isDemo"] and item["name"].startswith("Demo ") for item in body)
    assert all("not a real facility" in item["description"] for item in body)
    assert names(response) == sorted(names(response))


def test_operator_contact_details_are_never_public(client):
    listing = client.get(f"{API}/facilities").text
    detail = client.get(f"{API}/facilities/{facility_named('Demo Rally Center').id}").text
    for text in (listing, detail):
        assert "demo.operator@courtmate.demo" not in text
        assert "contact" not in text.lower()
        assert "verificationNotes" not in text
        assert "ownerUserId" not in text


def test_unverified_facilities_are_hidden(client, db):
    owner = db.query(User).first()
    pending = Facility(name="Pending Place", slug="pending-place", region_code="130000000", city_code="137404000", owner_user_id=owner.id)
    db.add(pending)
    db.commit()
    assert "Pending Place" not in names(client.get(f"{API}/facilities"))
    assert client.get(f"{API}/facilities/{pending.id}").status_code == 404
    assert client.get(f"{API}/facilities/{pending.id}/availability").status_code == 404


def test_filter_by_sport(client):
    assert names(client.get(f"{API}/facilities", params={"sportId": "bowling"})) == ["Demo Strike and Cue Lounge"]
    assert names(client.get(f"{API}/facilities", params={"sportId": "basketball"})) == ["Demo Hoops and Spikes Arena"]
    assert names(client.get(f"{API}/facilities", params={"sportId": "esports"})) == []


def test_filter_by_location_levels(client):
    assert names(client.get(f"{API}/facilities", params={"regionCode": "130000000"})) == ["Demo Rally Center"]
    central_luzon = names(client.get(f"{API}/facilities", params={"regionCode": "030000000"}))
    assert central_luzon == ["Demo Hoops and Spikes Arena", "Demo Strike and Cue Lounge"]
    assert names(client.get(f"{API}/facilities", params={"provinceCode": "031400000"})) == ["Demo Hoops and Spikes Arena"]
    assert names(client.get(f"{API}/facilities", params={"cityCode": "043428000"})) == ["Demo Aquatic and Fitness Club"]
    assert names(client.get(f"{API}/facilities", params={"barangayCode": "137404011"})) == ["Demo Rally Center"]
    assert names(client.get(f"{API}/facilities", params={"regionCode": "150000000"})) == []


def test_filter_by_resource_type_and_text(client):
    assert names(client.get(f"{API}/facilities", params={"resourceType": "lane"})) == ["Demo Strike and Cue Lounge"]
    assert names(client.get(f"{API}/facilities", params={"resourceType": "pool_lane"})) == ["Demo Aquatic and Fitness Club"]
    assert names(client.get(f"{API}/facilities", params={"q": "golf"})) == ["Demo Greens Golf Course"]


def test_nearby_search_orders_by_distance(client):
    close = client.get(f"{API}/facilities", params={"lat": QC[0], "lng": QC[1], "radiusKm": 5})
    assert names(close) == ["Demo Rally Center"]
    assert close.json()[0]["distanceKm"] == 0

    wider = client.get(f"{API}/facilities", params={"lat": QC[0], "lng": QC[1], "radiusKm": 70})
    assert names(wider) == [
        "Demo Rally Center",
        "Demo Hoops and Spikes Arena",
        "Demo Aquatic and Fitness Club",
        "Demo Strike and Cue Lounge",
    ]
    distances = [item["distanceKm"] for item in wider.json()]
    assert distances == sorted(distances)
    assert 25 < distances[1] < 35  # Quezon City to Malolos
    assert wider.headers["x-total-count"] == "4"


def test_nearby_search_needs_both_coordinates(client):
    assert client.get(f"{API}/facilities", params={"lat": 14.6}).status_code == 422
    assert client.get(f"{API}/facilities", params={"lat": 140, "lng": 121}).status_code == 422


def test_pagination(client):
    first = client.get(f"{API}/facilities", params={"limit": 2})
    second = client.get(f"{API}/facilities", params={"limit": 2, "offset": 2})
    assert len(first.json()) == len(second.json()) == 2
    assert not set(names(first)) & set(names(second))


def test_facility_detail(client):
    facility = facility_named("Demo Hoops and Spikes Arena")
    body = client.get(f"{API}/facilities/{facility.id}").json()
    assert body["location"]["province"]["name"] == "Bulacan"
    assert body["location"]["region"]["name"] == "Central Luzon"
    assert body["location"]["barangay"]["name"] == "Bulihan"
    assert body["timezone"] == "Asia/Manila"
    assert len(body["hours"]) == 7 and body["hours"][0]["openLabel"] == "6:00 AM" and body["hours"][0]["closeLabel"] == "10:00 PM"
    assert body["bookingRules"]["requiresApproval"] is True
    by_name = {item["name"]: item for item in body["resources"]}
    assert set(by_name) == {"Main Court", "Half Court A", "Half Court B", "Volleyball Court"}
    main = by_name["Main Court"]
    assert sorted(main["childIds"]) == sorted([by_name["Half Court A"]["id"], by_name["Half Court B"]["id"]])
    assert by_name["Half Court A"]["parentId"] == main["id"]
    assert by_name["Half Court A"]["resourceType"]["id"] == "half_court"
    assert body["fromRateCentavos"] == 65000
    # The slug works as an address too.
    assert client.get(f"{API}/facilities/demo-hoops-and-spikes-arena").json()["id"] == facility.id


def test_ncr_facility_has_no_province(client):
    body = client.get(f"{API}/facilities/demo-rally-center").json()
    assert body["location"]["province"] is None
    assert body["location"]["city"]["name"] == "Quezon City"


def test_availability_reflects_seeded_bookings_and_blocks(client):
    facility = facility_named("Demo Rally Center")
    tomorrow = dt.datetime.now(MANILA).date() + dt.timedelta(days=1)
    body = client.get(f"{API}/facilities/{facility.id}/availability", params={"date": tomorrow.isoformat()}).json()
    assert body["isOpen"] and body["openMinute"] == 360 and body["closeMinute"] == 1320
    by_name = {item["resource"]["name"]: item["slots"] for item in body["resources"]}

    def status_at(resource, hour):
        target = dt.datetime.combine(tomorrow, dt.time(hour), tzinfo=MANILA).astimezone(dt.UTC)
        return next(slot["status"] for slot in by_name[resource] if dt.datetime.fromisoformat(slot["startAt"]) == target)

    assert len(by_name["Pickleball Court 1"]) == 16  # 06:00–22:00 in one-hour slots
    assert len(by_name["Table 1"]) == 32  # half-hour slots
    assert status_at("Pickleball Court 1", 18) == status_at("Pickleball Court 1", 19) == "booked"
    assert status_at("Pickleball Court 1", 17) == "available"
    assert status_at("Pickleball Court 3", 18) == "available"
    assert status_at("Badminton Court 4", 9) == "blocked"
    assert status_at("Badminton Court 4", 12) == "available"
    assert by_name["Pickleball Court 1"][0]["priceCentavos"] == 40000
    assert by_name["Table 1"][0]["priceCentavos"] == 7500


def test_availability_can_be_narrowed_to_a_sport(client):
    body = client.get(f"{API}/facilities/demo-rally-center/availability", params={"sportId": "table_tennis"}).json()
    assert [item["resource"]["name"] for item in body["resources"]] == ["Table 1", "Table 2"]


def test_availability_slots_are_utc_instants_for_manila_wall_time(client):
    day = dt.datetime.now(MANILA).date() + dt.timedelta(days=3)
    body = client.get(f"{API}/facilities/demo-rally-center/availability", params={"date": day.isoformat()}).json()
    first = body["resources"][0]["slots"][0]
    # 06:00 in Manila is 22:00 UTC on the previous day.
    assert first["startAt"] == f"{(day - dt.timedelta(days=1)).isoformat()}T22:00:00Z"


def test_availability_rejects_far_dates(client):
    assert client.get(f"{API}/facilities/demo-rally-center/availability", params={"date": "2031-01-01"}).status_code == 422


def test_past_slots_today_are_not_available(client):
    body = client.get(f"{API}/facilities/demo-rally-center/availability").json()
    now = dt.datetime.now(dt.UTC)
    for item in body["resources"]:
        for slot in item["slots"]:
            if dt.datetime.fromisoformat(slot["startAt"]) < now:
                assert slot["status"] in {"past", "booked", "blocked"}
