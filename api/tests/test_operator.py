import datetime as dt

from .conftest import API, facility_named, iso, manila, new_user, resource_named
from .test_booking import book

RALLY = "Demo Rally Center"
NEW_VENUE = {
    "name": "Malolos Smash Hub",
    "description": "Four wooden courts beside the public market.",
    "addressLine": "12 Sample Street",
    "cityCode": "031410000",
    "barangayCode": "031410012",
    "latitude": 14.8433,
    "longitude": 120.8114,
    "amenities": ["Parking", "Showers"],
    "sportIds": ["badminton"],
    "contactName": "Maria Santos",
    "contactEmail": "maria@example.com",
    "contactPhone": "+63 917 000 0000",
}
MORNINGS = [{"weekday": day, "openMinute": 480, "closeMinute": 720} for day in range(7)]


def register(client, headers, **overrides):
    response = client.post(f"{API}/operator/facilities", headers=headers, json={**NEW_VENUE, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def add_resource(client, headers, facility_id, name, **overrides):
    payload = {
        "name": name,
        "resourceTypeId": "court",
        "sportIds": ["badminton"],
        "capacity": 4,
        "slotMinutes": 60,
        "hourlyRateCentavos": 30000,
        **overrides,
    }
    return client.post(f"{API}/operator/facilities/{facility_id}/resources", headers=headers, json=payload)


def onboard(client, admin, **overrides):
    """Register, schedule, equip and verify a venue. Returns (owner headers, facility)."""
    _, owner = new_user("Venue Owner")
    facility = register(client, owner, **overrides)
    client.put(f"{API}/operator/facilities/{facility['id']}/hours", headers=owner, json=MORNINGS)
    add_resource(client, owner, facility["id"], "Court A")
    add_resource(client, owner, facility["id"], "Court B")
    verified = client.post(f"{API}/admin/facilities/{facility['id']}/verification", headers=admin, json={"status": "verified"})
    assert verified.status_code == 200, verified.text
    return owner, client.get(f"{API}/operator/facilities/{facility['id']}", headers=owner).json()


def court(facility, name):
    return next(item for item in facility["resources"] if item["name"] == name)


# --- access -------------------------------------------------------------------


def test_demo_operator_sees_their_facilities_with_private_fields(client, operator):
    facilities = client.get(f"{API}/operator/facilities", headers=operator).json()
    assert len(facilities) == 6
    assert facilities[0]["contactEmail"] == "demo.operator@courtmate.demo" and facilities[0]["staff"][0]["role"] == "owner"


def test_dashboard_is_closed_to_everyone_else(client, player):
    facility = facility_named(RALLY)
    table = resource_named(RALLY, "Table 1")
    assert client.get(f"{API}/operator/facilities").status_code == 401
    assert client.get(f"{API}/operator/facilities", headers=player).json() == []
    for method, path, body in [
        ("get", f"/operator/facilities/{facility.id}", None),
        ("patch", f"/operator/facilities/{facility.id}", {"name": "Hijacked Hall"}),
        ("put", f"/operator/facilities/{facility.id}/hours", []),
        ("post", f"/operator/facilities/{facility.id}/resources", {"name": "X", "resourceTypeId": "court", "sportIds": ["badminton"]}),
        ("get", f"/operator/facilities/{facility.id}/reservations", None),
        ("get", f"/operator/facilities/{facility.id}/occupancy", None),
        ("patch", f"/operator/resources/{table.id}", {"hourlyRateCentavos": 1}),
        ("post", f"/operator/resources/{table.id}/blocks", {"startAt": iso(manila(3, 10)), "endAt": iso(manila(3, 11))}),
    ]:
        response = getattr(client, method)(f"{API}{path}", headers=player, **({"json": body} if body is not None else {}))
        assert response.status_code == 404, (method, path, response.status_code)


# --- registration and verification -------------------------------------------


def test_a_new_facility_is_private_until_verified(client, admin, player):
    _, owner = new_user("Venue Owner")
    facility = register(client, owner)
    assert facility["verificationStatus"] == "pending" and facility["isDemo"] is False
    assert facility["location"]["barangay"]["name"] == "Bulihan" and facility["location"]["province"]["name"] == "Bulacan"
    assert facility["contactEmail"] == "maria@example.com"

    assert "Malolos Smash Hub" not in [item["name"] for item in client.get(f"{API}/facilities").json()]
    assert client.get(f"{API}/facilities/{facility['id']}").status_code == 404
    assert [item["name"] for item in client.get(f"{API}/operator/facilities", headers=owner).json()] == ["Malolos Smash Hub"]

    url = f"{API}/admin/facilities/{facility['id']}/verification"
    assert client.post(url, headers=owner, json={"status": "verified"}).status_code == 403
    assert client.post(url, headers=player, json={"status": "verified"}).status_code == 403
    assert client.get(f"{API}/admin/facilities", headers=owner).status_code == 403

    queue = client.get(f"{API}/admin/facilities", headers=admin).json()
    assert [item["name"] for item in queue] == ["Malolos Smash Hub"]
    assert queue[0]["contactPhone"] == "+63 917 000 0000" and queue[0]["owner"]["displayName"] == "Venue Owner"

    verified = client.post(url, headers=admin, json={"status": "verified", "notes": "Business permit checked."}).json()
    assert verified["verificationStatus"] == "verified"
    public = client.get(f"{API}/facilities/{facility['id']}")
    assert public.status_code == 200
    assert "maria@example.com" not in public.text and "Maria Santos" not in public.text and "Business permit" not in public.text
    notice = client.get(f"{API}/notifications", headers=owner).json()["items"][0]
    assert notice["title"] == "Facility verified" and notice["link"] == f"/operator/{facility['id']}"
    assert client.get(f"{API}/admin/facilities", headers=admin).json() == []


def test_rejection_and_suspension(client, admin):
    owner, facility = onboard(client, admin)
    url = f"{API}/admin/facilities/{facility['id']}/verification"
    suspended = client.post(url, headers=admin, json={"status": "suspended", "notes": "Reported closed."}).json()
    assert suspended["verificationNotes"] == "Reported closed."
    assert client.get(f"{API}/facilities/{facility['id']}").status_code == 404
    assert book(client, new_user("Hopeful")[1], type("R", (), {"id": court(facility, "Court A")["id"]}), manila(3, 9)).status_code == 404
    assert client.get(f"{API}/operator/facilities/{facility['id']}", headers=owner).json()["verificationNotes"] == "Reported closed."
    assert client.post(f"{API}/admin/facilities/nope/verification", headers=admin, json={"status": "verified"}).status_code == 404


def test_registration_validation(client):
    _, owner = new_user("Venue Owner")

    def rejected(**overrides):
        response = client.post(f"{API}/operator/facilities", headers=owner, json={**NEW_VENUE, **overrides})
        assert response.status_code == 422, response.text
        return str(response.json()["detail"])

    assert "meet outdoors" in rejected(sportIds=["running"])
    assert "Unknown sport" in rejected(sportIds=["quidditch"])
    assert "barangay is not in" in rejected(cityCode="137404000")
    assert "Unknown city" in rejected(cityCode="000000000", barangayCode=None)
    rejected(contactEmail="not-an-email")
    rejected(contactPhone="call me maybe")
    rejected(latitude=14.8, longitude=None)
    assert client.post(f"{API}/operator/facilities", json=NEW_VENUE).status_code == 401


# --- running the venue --------------------------------------------------------


def test_onboarded_venue_takes_bookings(client, admin):
    owner, facility = onboard(client, admin)
    assert [item["name"] for item in facility["resources"]] == ["Court A", "Court B"]
    assert facility["hours"][0]["openLabel"] == "8:00 AM" and len(facility["hours"]) == 7
    day = manila(3, 0).date()
    slots = client.get(f"{API}/facilities/{facility['id']}/availability", params={"date": day.isoformat()}).json()["resources"][0]["slots"]
    assert [slot["status"] for slot in slots] == ["available"] * 4 and slots[0]["priceCentavos"] == 30000

    _, customer = new_user("Paying Customer")
    resource = type("R", (), {"id": court(facility, "Court A")["id"]})
    assert book(client, customer, resource, manila(3, 9)).json()[0]["status"] == "confirmed"
    assert book(client, customer, resource, manila(3, 13)).status_code == 422  # after closing


def test_approval_flow_notifies_both_sides(client, admin):
    owner, facility = onboard(client, admin)
    patched = client.patch(
        f"{API}/operator/facilities/{facility['id']}", headers=owner, json={"requiresApproval": True, "cancellationWindowHours": 12}
    )
    assert patched.json()["bookingRules"]["requiresApproval"] is True and patched.json()["bookingRules"]["cancellationWindowHours"] == 12

    customer_id, customer = new_user("Paying Customer")
    resource = type("R", (), {"id": court(facility, "Court A")["id"]})
    [first] = book(client, customer, resource, manila(3, 8)).json()
    [second] = book(client, customer, resource, manila(3, 10)).json()
    assert first["status"] == second["status"] == "pending"

    inbox = client.get(f"{API}/notifications", headers=owner).json()["items"]
    assert [item["kind"] for item in inbox].count("booking_request") == 2 and "Paying Customer asked for Court A" in inbox[0]["body"]
    assert client.get(f"{API}/operator/facilities/{facility['id']}", headers=owner).json()["pendingRequests"] == 2
    pending = client.get(f"{API}/operator/facilities/{facility['id']}/reservations", headers=owner, params={"scope": "pending"}).json()
    assert [item["id"] for item in pending] == [first["id"], second["id"]] and pending[0]["organizer"]["displayName"] == "Paying Customer"

    stranger = new_user("Stranger")[1]
    assert client.post(f"{API}/operator/reservations/{first['id']}/confirm", headers=stranger).status_code == 404
    assert client.post(f"{API}/operator/reservations/{first['id']}/confirm", headers=customer).status_code == 404

    assert client.post(f"{API}/operator/reservations/{first['id']}/confirm", headers=owner).json()["status"] == "confirmed"
    rejected = client.post(f"{API}/operator/reservations/{second['id']}/reject", headers=owner, json={"reason": "Private event."}).json()
    assert rejected["status"] == "rejected" and rejected["cancelReason"] == "Private event."
    assert client.post(f"{API}/operator/reservations/{second['id']}/reject", headers=owner).status_code == 409

    mine = client.get(f"{API}/notifications", headers=customer).json()["items"]
    assert {item["title"] for item in mine} == {"Booking confirmed", "Booking declined"}
    assert any("Private event." in item["body"] for item in mine)
    # The rejected hour is bookable again.
    assert book(client, new_user("Next In Line")[1], resource, manila(3, 10)).status_code == 201


def test_venue_and_customer_cancellations(client, admin):
    owner, facility = onboard(client, admin)
    customer_id, customer = new_user("Paying Customer")
    resource = type("R", (), {"id": court(facility, "Court A")["id"]})
    [by_venue] = book(client, customer, resource, manila(3, 8)).json()
    [by_customer] = book(client, customer, resource, manila(3, 10)).json()

    cancelled = client.post(f"{API}/operator/reservations/{by_venue['id']}/cancel", headers=owner, json={"reason": "Roof leak."}).json()
    assert cancelled["status"] == "cancelled" and cancelled["lateCancellation"] is False
    notice = client.get(f"{API}/notifications", headers=customer).json()["items"][0]
    assert notice["title"] == "Booking cancelled by the venue" and "Roof leak." in notice["body"]

    client.post(f"{API}/reservations/{by_customer['id']}/cancel", headers=customer)
    assert client.get(f"{API}/notifications", headers=owner).json()["items"][0]["body"] == "Paying Customer cancelled Court A."

    history = client.get(f"{API}/operator/facilities/{facility['id']}/reservations", headers=owner, params={"scope": "past"}).json()
    assert {item["status"] for item in history} == {"cancelled"} and len(history) == 2
    assert client.get(f"{API}/operator/facilities/{facility['id']}/reservations", headers=owner).json() == []


def test_blocks(client, admin):
    owner, facility = onboard(client, admin)
    resource_id = court(facility, "Court A")["id"]
    resource = type("R", (), {"id": resource_id})
    _, customer = new_user("Paying Customer")
    book(client, customer, resource, manila(3, 11))

    def block(start, hours, reason="Resurfacing"):
        payload = {"startAt": iso(start), "endAt": iso(start + dt.timedelta(hours=hours)), "reason": reason}
        return client.post(f"{API}/operator/resources/{resource_id}/blocks", headers=owner, json=payload)

    clash = block(manila(3, 10), 2)
    assert clash.status_code == 409 and "bookings in that period" in clash.json()["detail"]
    created = block(manila(3, 8), 2)
    assert created.status_code == 201 and created.json()["kind"] == "block" and created.json()["note"] == "Resurfacing"
    assert book(client, customer, resource, manila(3, 9)).status_code == 409
    assert block(manila(3, 8, 10), 1).status_code == 422
    assert block(manila(3, 8), 24 * 8).status_code == 422

    listed = client.get(f"{API}/operator/facilities/{facility['id']}/reservations", headers=owner, params={"scope": "blocks"}).json()
    assert [item["id"] for item in listed] == [created.json()["id"]]
    slots = client.get(f"{API}/resources/{resource_id}/availability", params={"date": manila(3, 0).date().isoformat()}).json()["resources"][
        0
    ]["slots"]
    assert [slot["status"] for slot in slots] == ["blocked", "blocked", "available", "booked"]

    assert client.delete(f"{API}/operator/blocks/{created.json()['id']}", headers=new_user("Stranger")[1]).status_code == 404
    assert client.delete(f"{API}/operator/blocks/{created.json()['id']}", headers=owner).status_code == 204
    assert book(client, customer, resource, manila(3, 9)).status_code == 201
    # A customer's booking cannot be deleted through the block route.
    booking_id = client.get(f"{API}/reservations", headers=customer).json()[0]["id"]
    assert client.delete(f"{API}/operator/blocks/{booking_id}", headers=owner).status_code == 404


def test_resources(client, admin):
    owner, facility = onboard(client, admin)
    facility_id = facility["id"]
    assert add_resource(client, owner, facility_id, "Court A").status_code == 409
    assert add_resource(client, owner, facility_id, "Court C", resourceTypeId="hoverpad").status_code == 422
    assert add_resource(client, owner, facility_id, "Court C", slotMinutes=50).status_code == 422
    assert "meet outdoors" in add_resource(client, owner, facility_id, "Track", sportIds=["running"]).json()["detail"]

    # A resource for a new sport adds that sport to the facility.
    with_pickleball = add_resource(client, owner, facility_id, "Court C", sportIds=["pickleball"]).json()
    assert {sport["id"] for sport in with_pickleball["sports"]} == {"badminton", "pickleball"}

    court_a = court(facility, "Court A")
    patched = client.patch(
        f"{API}/operator/resources/{court_a['id']}",
        headers=owner,
        json={"hourlyRateCentavos": 45000, "capacity": 6, "name": "Centre Court"},
    )
    assert court(patched.json(), "Centre Court")["hourlyRateCentavos"] == 45000
    assert client.get(f"{API}/facilities/{facility_id}").json()["fromRateCentavos"] == 30000

    off = client.patch(f"{API}/operator/resources/{court_a['id']}", headers=owner, json={"isActive": False}).json()
    assert court(off, "Centre Court")["isActive"] is False  # the operator still sees it
    assert "Centre Court" not in [item["name"] for item in client.get(f"{API}/facilities/{facility_id}").json()["resources"]]
    assert book(client, new_user("Customer")[1], type("R", (), {"id": court_a["id"]}), manila(3, 9)).status_code == 409


def test_dividing_a_space_into_sections(client, admin):
    owner, facility = onboard(client, admin)
    facility_id = facility["id"]
    court_a, court_b = court(facility, "Court A"), court(facility, "Court B")
    _, customer = new_user("Paying Customer")
    book(client, customer, type("R", (), {"id": court_b["id"]}), manila(3, 9))

    halved = add_resource(client, owner, facility_id, "Court A North", resourceTypeId="half_court", parentId=court_a["id"])
    assert halved.status_code == 201
    north = court(halved.json(), "Court A North")
    assert north["parentId"] == court_a["id"] and court(halved.json(), "Court A")["childIds"] == [north["id"]]
    assert "cannot itself be divided" in add_resource(client, owner, facility_id, "Quarter", parentId=north["id"]).json()["detail"]
    # Court B has a booking held against it, so it cannot be divided yet.
    assert "upcoming bookings" in add_resource(client, owner, facility_id, "Court B North", parentId=court_b["id"]).json()["detail"]
    elsewhere = resource_named(RALLY, "Table 1")
    assert add_resource(client, owner, facility_id, "Borrowed", parentId=elsewhere.id).status_code == 422


def test_hours_and_rules_validation(client, admin):
    owner, facility = onboard(client, admin)
    url = f"{API}/operator/facilities/{facility['id']}"
    weekdays_only = [{"weekday": day, "openMinute": 360, "closeMinute": 1320} for day in range(5)]
    updated = client.put(f"{url}/hours", headers=owner, json=weekdays_only).json()
    assert [item["weekday"] for item in updated["hours"]] == [0, 1, 2, 3, 4]
    saturday = next(manila(offset, 0).date() for offset in range(1, 8) if manila(offset, 0).weekday() == 5)
    assert client.get(f"{API}/facilities/{facility['id']}/availability", params={"date": saturday.isoformat()}).json()["isOpen"] is False

    assert client.put(f"{url}/hours", headers=owner, json=[*weekdays_only, weekdays_only[0]]).status_code == 422
    assert client.put(f"{url}/hours", headers=owner, json=[{"weekday": 0, "openMinute": 600, "closeMinute": 540}]).status_code == 422
    assert client.put(f"{url}/hours", headers=owner, json=[{"weekday": 0, "openMinute": 605, "closeMinute": 900}]).status_code == 422
    assert client.patch(url, headers=owner, json={"minBookingMinutes": 120, "maxBookingMinutes": 60}).status_code == 422

    moved = client.patch(url, headers=owner, json={"cityCode": "137404000", "contactName": "New Manager", "amenities": ["Lockers"]}).json()
    assert (
        moved["location"]["city"]["name"] == "Quezon City"
        and moved["location"]["barangay"] is None
        and moved["location"]["province"] is None
    )
    assert moved["contactName"] == "New Manager" and moved["amenities"] == ["Lockers"]


def test_occupancy_report(client, admin):
    owner, facility = onboard(client, admin)
    facility_id = facility["id"]
    court_a, court_b = court(facility, "Court A"), court(facility, "Court B")
    _, customer = new_user("Paying Customer")
    day = manila(3, 0).date()

    book(client, customer, type("R", (), {"id": court_a["id"]}), manila(3, 8), minutes=120)
    [dropped] = book(client, customer, type("R", (), {"id": court_a["id"]}), manila(3, 11)).json()
    client.post(f"{API}/reservations/{dropped['id']}/cancel", headers=customer)
    block = {"startAt": iso(manila(3, 10)), "endAt": iso(manila(3, 11)), "reason": "Net repair"}
    client.post(f"{API}/operator/resources/{court_b['id']}/blocks", headers=owner, json=block)

    report = client.get(
        f"{API}/operator/facilities/{facility_id}/occupancy", headers=owner, params={"from": day.isoformat(), "to": day.isoformat()}
    ).json()
    by_name = {item["name"]: item for item in report["resources"]}
    assert by_name["Court A"] == {
        **by_name["Court A"],
        "openMinutes": 240,
        "bookedMinutes": 120,
        "blockedMinutes": 0,
        "occupancyPercent": 50.0,
    }
    assert by_name["Court B"]["bookedMinutes"] == 0 and by_name["Court B"]["blockedMinutes"] == 60
    assert report["openMinutes"] == 480 and report["bookedMinutes"] == 120 and report["occupancyPercent"] == 25.0
    assert report["confirmedBookings"] == 1 and report["cancelledBookings"] == 1 and report["pendingBookings"] == 0
    assert report["bookedValueCentavos"] == 60000

    week = client.get(f"{API}/operator/facilities/{facility_id}/occupancy", headers=owner).json()
    assert week["openMinutes"] == 480 * 7
    too_long = {"from": day.isoformat(), "to": (day + dt.timedelta(days=120)).isoformat()}
    assert client.get(f"{API}/operator/facilities/{facility_id}/occupancy", headers=owner, params=too_long).status_code == 422


def test_full_court_bookings_count_on_each_section(client, operator):
    arena = facility_named("Demo Hoops and Spikes Arena")
    main = resource_named(arena.name, "Main Court")
    day = manila(3, 0).date()
    [pending] = book(client, new_user("Team Captain")[1], main, manila(3, 10), minutes=120).json()
    client.post(f"{API}/operator/reservations/{pending['id']}/confirm", headers=operator)
    report = client.get(
        f"{API}/operator/facilities/{arena.id}/occupancy", headers=operator, params={"from": day.isoformat(), "to": day.isoformat()}
    ).json()
    by_name = {item["name"]: item["bookedMinutes"] for item in report["resources"]}
    assert by_name == {"Half Court A": 120, "Half Court B": 120, "Volleyball Court": 0}
    assert report["bookedValueCentavos"] == 240000


def test_reservation_list_filters(client, operator, player):
    rally = facility_named(RALLY)
    court_three = resource_named(RALLY, "Pickleball Court 3")
    book(client, player, court_three, manila(3, 10))
    book(client, player, court_three, manila(4, 10))
    url = f"{API}/operator/facilities/{rally.id}/reservations"
    on_day = client.get(url, headers=operator, params={"date": manila(3, 0).date().isoformat()}).json()
    assert len(on_day) == 1 and on_day[0]["resource"]["name"] == "Pickleball Court 3"
    upcoming = client.get(url, headers=operator).json()
    assert len(upcoming) == 5  # three seeded bookings plus these two
    assert [item["startAt"] for item in upcoming] == sorted(item["startAt"] for item in upcoming)
    assert len(client.get(url, headers=operator, params={"scope": "blocks"}).json()) == 1
    assert "@" not in client.get(url, headers=operator).text


def test_operator_schedule_works_before_verification(client):
    _, owner = new_user("Venue Owner")
    facility = register(client, owner)
    client.put(f"{API}/operator/facilities/{facility['id']}/hours", headers=owner, json=MORNINGS)
    add_resource(client, owner, facility["id"], "Court A")
    day = manila(3, 0).date().isoformat()
    schedule = client.get(f"{API}/operator/facilities/{facility['id']}/availability", headers=owner, params={"date": day})
    assert schedule.status_code == 200 and len(schedule.json()["resources"][0]["slots"]) == 4
    # Not verified yet, so nothing is open to book.
    assert {slot["status"] for slot in schedule.json()["resources"][0]["slots"]} == {"closed"}
    assert client.get(f"{API}/operator/facilities/{facility['id']}/availability", headers=new_user("Stranger")[1]).status_code == 404
