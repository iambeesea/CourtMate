import datetime as dt
import threading

from sqlalchemy import func, select

from app import db as database
from app.models import Facility, Reservation, ReservationSlot, User
from app.services import booking

from .conftest import API, demo_headers, iso, manila, new_user, resource_named, scalar

RALLY = "Demo Rally Center"
ARENA = "Demo Hoops and Spikes Arena"


def book(client, headers, resource, start, minutes=60, **extra):
    payload = {"resourceId": resource.id, "startAt": iso(start), "endAt": iso(start + dt.timedelta(minutes=minutes)), **extra}
    return client.post(f"{API}/reservations", headers=headers, json=payload)


def test_booking_requires_sign_in(client):
    court = resource_named(RALLY, "Pickleball Court 3")
    assert book(client, {}, court, manila(3, 10)).status_code == 401


def test_book_a_court(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    response = book(client, player, court, manila(3, 10), minutes=120, sportId="pickleball", partySize=4, note="Bringing balls")
    assert response.status_code == 201, response.text
    [reservation] = response.json()
    assert reservation["status"] == "confirmed"
    assert reservation["priceCentavos"] == 80000
    assert reservation["paymentStatus"] == "pay_at_venue"
    assert reservation["sport"]["id"] == "pickleball"
    assert reservation["facility"]["isDemo"] is True
    assert reservation["canCancel"] is True
    # 10:00 in Manila is stored and returned as 02:00 UTC.
    assert reservation["startAt"].endswith("T02:00:00Z")
    start = dt.datetime.fromisoformat(reservation["startAt"])
    assert dt.datetime.fromisoformat(reservation["freeCancelUntil"]) == start - dt.timedelta(hours=24)


def test_the_same_slot_cannot_be_booked_twice(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    _, other = new_user("Second Player")
    assert book(client, player, court, manila(3, 10)).status_code == 201
    clash = book(client, other, court, manila(3, 10))
    assert clash.status_code == 409
    assert "taken" in clash.json()["detail"]


def test_overlapping_bookings_are_rejected_but_adjacent_ones_are_fine(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    assert book(client, player, court, manila(3, 10), minutes=120).status_code == 201
    assert book(client, player, court, manila(3, 11), minutes=120).status_code == 409
    assert book(client, player, court, manila(3, 9), minutes=120).status_code == 409
    assert book(client, player, court, manila(3, 12)).status_code == 201
    assert book(client, player, court, manila(3, 9)).status_code == 201


def test_a_failed_booking_leaves_nothing_behind(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    slots = select(func.count()).select_from(ReservationSlot)
    before = scalar(slots)
    book(client, player, court, manila(3, 10))
    assert book(client, player, court, manila(3, 10)).status_code == 409
    assert scalar(select(func.count()).select_from(Reservation).where(Reservation.resource_id == court.id)) == 1
    assert scalar(slots) == before + 4


def test_time_validation(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    table = resource_named(RALLY, "Table 1")
    assert "15-minute" in book(client, player, court, manila(3, 10, 7)).json()["detail"]
    assert "60-minute blocks" in book(client, player, court, manila(3, 10), minutes=90).json()["detail"]
    assert "opening hours" in book(client, player, court, manila(3, 5)).json()["detail"]
    assert "opening hours" in book(client, player, court, manila(3, 21), minutes=120).json()["detail"]
    assert "start every 60 minutes" in book(client, player, court, manila(3, 10, 30)).json()["detail"]
    assert "maximum booking" in book(client, player, court, manila(3, 10), minutes=240).json()["detail"]
    assert "already passed" in book(client, player, court, manila(-1, 10)).json()["detail"]
    assert "days ahead" in book(client, player, court, manila(45, 10)).json()["detail"]
    assert book(client, player, table, manila(3, 10, 30), minutes=30).status_code == 201
    backwards = {"resourceId": court.id, "startAt": iso(manila(3, 11)), "endAt": iso(manila(3, 10))}
    assert client.post(f"{API}/reservations", headers=player, json=backwards).status_code == 422
    naive = {"resourceId": court.id, "startAt": "2030-01-01T10:00:00", "endAt": "2030-01-01T11:00:00"}
    assert client.post(f"{API}/reservations", headers=player, json=naive).status_code == 422


def test_minimum_notice(client, player, db):
    facility = db.scalar(select(Facility).where(Facility.name == RALLY))
    facility.min_notice_minutes = 60 * 24 * 2
    db.commit()
    court = resource_named(RALLY, "Pickleball Court 3")
    assert "notice" in book(client, player, court, manila(1, 10)).json()["detail"]
    assert book(client, player, court, manila(4, 10)).status_code == 201


def test_party_size_and_sport_must_fit_the_resource(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    assert "holds up to 4" in book(client, player, court, manila(3, 10), partySize=9).json()["detail"]
    assert "not set up for that sport" in book(client, player, court, manila(3, 10), sportId="bowling").json()["detail"]
    assert (
        client.post(
            f"{API}/reservations",
            headers=player,
            json={"resourceId": "missing", "startAt": iso(manila(3, 10)), "endAt": iso(manila(3, 11))},
        ).status_code
        == 404
    )


def test_full_court_and_half_courts_share_time(client, player):
    full = resource_named(ARENA, "Main Court")
    half_a = resource_named(ARENA, "Half Court A")
    half_b = resource_named(ARENA, "Half Court B")
    volleyball = resource_named(ARENA, "Volleyball Court")

    assert book(client, player, half_a, manila(3, 10)).status_code == 201
    assert book(client, player, full, manila(3, 10)).status_code == 409  # one half is taken
    assert book(client, player, half_b, manila(3, 10)).status_code == 201  # the other half is free
    assert book(client, player, half_a, manila(3, 10)).status_code == 409

    assert book(client, player, full, manila(3, 14)).status_code == 201
    assert book(client, player, half_a, manila(3, 14)).status_code == 409  # the full court holds both halves
    assert book(client, player, half_b, manila(3, 14)).status_code == 409
    assert book(client, player, volleyball, manila(3, 14)).status_code == 201  # unrelated court


def test_availability_shows_a_half_booking_on_the_full_court(client, player):
    half_a = resource_named(ARENA, "Half Court A")
    start = manila(3, 10)
    book(client, player, half_a, start)
    body = client.get(f"{API}/facilities/demo-hoops-and-spikes-arena/availability", params={"date": start.date().isoformat()}).json()
    by_name = {item["resource"]["name"]: item["slots"] for item in body["resources"]}
    at_ten = lambda name: next(s["status"] for s in by_name[name] if dt.datetime.fromisoformat(s["startAt"]) == start)  # noqa: E731
    assert at_ten("Half Court A") == "booked"
    assert at_ten("Main Court") == "booked"
    assert at_ten("Half Court B") == "available"


def test_approval_facility_holds_the_slot_while_pending(client, player):
    court = resource_named(ARENA, "Volleyball Court")
    [reservation] = book(client, player, court, manila(3, 10)).json()
    assert reservation["status"] == "pending"
    _, other = new_user("Second Player")
    assert book(client, other, court, manila(3, 10)).status_code == 409


def test_cancelling_frees_the_slot(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    _, other = new_user("Second Player")
    [reservation] = book(client, player, court, manila(3, 10)).json()
    cancelled = client.post(f"{API}/reservations/{reservation['id']}/cancel", headers=player, json={"reason": "Rain"})
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "cancelled" and body["cancelReason"] == "Rain" and body["canCancel"] is False
    assert body["lateCancellation"] is False
    assert book(client, other, court, manila(3, 10)).status_code == 201
    assert client.post(f"{API}/reservations/{reservation['id']}/cancel", headers=player).status_code == 409


def test_late_cancellation_is_flagged_for_the_organizer_only(client, player, db):
    court = resource_named(RALLY, "Pickleball Court 3")
    [late, by_staff] = [book(client, player, court, manila(3, hour)).json()[0] for hour in (10, 12)]
    organizer = db.scalar(select(User).where(User.email == "demo.player@courtmate.demo"))
    staff = db.scalar(select(User).where(User.email == "demo.operator@courtmate.demo"))

    # Two hours before the start is inside this facility's 24-hour free-cancellation window.
    reservation = db.get(Reservation, late["id"])
    booking.cancel(db, reservation, by=organizer, now=reservation.start_at - dt.timedelta(hours=2))
    assert reservation.status == "cancelled" and reservation.late_cancellation is True

    reservation = db.get(Reservation, by_staff["id"])
    booking.cancel(db, reservation, by=staff, now=reservation.start_at - dt.timedelta(hours=2))
    assert reservation.status == "cancelled" and reservation.late_cancellation is False
    db.commit()


def test_reservations_are_private_to_the_organizer_and_facility_staff(client, player, operator):
    court = resource_named(RALLY, "Pickleball Court 3")
    [reservation] = book(client, player, court, manila(3, 10)).json()
    _, stranger = new_user("Nosy Stranger")
    assert client.get(f"{API}/reservations/{reservation['id']}", headers=stranger).status_code == 404
    assert client.post(f"{API}/reservations/{reservation['id']}/cancel", headers=stranger).status_code == 404
    assert client.get(f"{API}/reservations/{reservation['id']}", headers=operator).status_code == 200
    assert client.get(f"{API}/reservations/{reservation['id']}").status_code == 401


def test_my_reservations(client, player, db):
    court = resource_named(RALLY, "Pickleball Court 3")
    [first] = book(client, player, court, manila(3, 10)).json()
    [second] = book(client, player, court, manila(2, 10)).json()
    client.post(f"{API}/reservations/{first['id']}/cancel", headers=player)
    upcoming = client.get(f"{API}/reservations", headers=player).json()
    assert [item["id"] for item in upcoming] == [second["id"]]
    past = client.get(f"{API}/reservations", headers=player, params={"scope": "past"}).json()
    assert [item["id"] for item in past] == [first["id"]]
    assert len(client.get(f"{API}/reservations", headers=player, params={"scope": "all"}).json()) == 2

    # A confirmed reservation whose time has passed reads as completed.
    record = db.get(Reservation, second["id"])
    record.start_at -= dt.timedelta(days=10)
    record.end_at -= dt.timedelta(days=10)
    db.commit()
    [finished] = [
        item for item in client.get(f"{API}/reservations", headers=player, params={"scope": "past"}).json() if item["id"] == second["id"]
    ]
    assert finished["status"] == "completed" and finished["canCancel"] is False


def test_weekly_series_is_all_or_nothing(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    _, other = new_user("Second Player")
    # Someone already holds week three.
    assert book(client, other, court, manila(3 + 14, 10)).status_code == 201

    clash = book(client, player, court, manila(3, 10), repeatWeeks=4)
    assert clash.status_code == 409
    assert "series was not booked" in clash.json()["detail"]
    assert client.get(f"{API}/reservations", headers=player).json() == []

    series = book(client, player, court, manila(3, 12), repeatWeeks=4)
    assert series.status_code == 201
    occurrences = series.json()
    assert len(occurrences) == 4
    assert len({item["seriesId"] for item in occurrences}) == 1
    starts = [dt.datetime.fromisoformat(item["startAt"]) for item in occurrences]
    assert all(later - earlier == dt.timedelta(weeks=1) for earlier, later in zip(starts, starts[1:], strict=False))


def test_series_cannot_run_past_the_advance_window(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    response = book(client, player, court, manila(3, 10), repeatWeeks=8)
    assert response.status_code == 422
    assert "days ahead" in response.json()["detail"]


def test_operator_block_prevents_booking(client, player, db):
    court = resource_named(RALLY, "Pickleball Court 3")
    facility = db.get(Facility, court.facility_id)
    staff = db.scalar(select(User).where(User.email == "demo.operator@courtmate.demo"))
    start = manila(3, 9).astimezone(dt.UTC)
    booking.create_block(db, facility=facility, resource=db.merge(court), staff=staff, start_at=start, end_at=start + dt.timedelta(hours=3))
    db.commit()
    assert book(client, player, court, manila(3, 10)).status_code == 409
    assert book(client, player, court, manila(3, 12)).status_code == 201


def test_active_booking_cap(client, player, monkeypatch):
    from app.routers import reservations

    monkeypatch.setattr(reservations, "MAX_ACTIVE_BOOKINGS", 2)
    court = resource_named(RALLY, "Pickleball Court 3")
    assert book(client, player, court, manila(3, 10)).status_code == 201
    assert book(client, player, court, manila(3, 11)).status_code == 201
    capped = book(client, player, court, manila(3, 12))
    assert capped.status_code == 409 and "up to 2" in capped.json()["detail"]


def test_concurrent_requests_for_one_slot_produce_one_booking(client, db_path):
    """Twelve players race for the same hour through separate connections; the slot key lets exactly one in."""
    court = resource_named(RALLY, "Pickleball Court 4")
    start = manila(4, 15).astimezone(dt.UTC)
    user_ids = [new_user(f"Racer {index}")[0] for index in range(12)]
    barrier = threading.Barrier(len(user_ids))
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(user_id: str) -> None:
        # Line everyone up first: on SQLite a session takes the write lock on its first statement.
        barrier.wait()
        with database.session_factory()() as session:
            resource = session.get(type(court), court.id)
            user = session.get(User, user_id)
            try:
                booking.create_booking(
                    session,
                    facility=resource.facility,
                    resource=resource,
                    organizer=user,
                    start_at=start,
                    end_at=start + dt.timedelta(hours=1),
                )
                session.commit()
                result = "booked"
            except booking.SlotTaken:
                session.rollback()
                result = "taken"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(user_id,)) for user_id in user_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert sorted(outcomes) == ["booked"] + ["taken"] * 11
    with database.session_factory()() as session:
        held = session.scalar(
            select(func.count()).select_from(Reservation).where(Reservation.resource_id == court.id, Reservation.start_at == start)
        )
        assert held == 1
    assert demo_headers(client)  # the API is still healthy afterwards
