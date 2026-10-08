import datetime as dt
import threading

from sqlalchemy import func, select

from app import db as database
from app.models import Notification, PlaySession, Reservation, SessionParticipant, User
from app.services import sessions as service

from .conftest import API, demo_headers, facility_named, headers_for, iso, manila, new_user, resource_named, scalar

RALLY = "Demo Rally Center"


def find(client, title, headers=None):
    return next(item for item in client.get(f"{API}/sessions", headers=headers or {}).json() if item["title"] == title)


def host_session(client, headers, **overrides):
    start = overrides.pop("start", manila(3, 10))
    payload = {
        "title": "Test Rally",
        "sportId": "pickleball",
        "kind": "open_play",
        "startAt": iso(start),
        "endAt": iso(start + dt.timedelta(hours=2)),
        "capacity": 4,
        "teamFormat": "doubles",
        "facilityId": facility_named(RALLY).id,
        **overrides,
    }
    return client.post(f"{API}/sessions", headers=headers, json=payload)


# --- discovery ----------------------------------------------------------------


def test_demo_sessions_cover_many_sports_and_are_labelled(client):
    response = client.get(f"{API}/sessions")
    sessions = response.json()
    assert response.headers["x-total-count"] == "14"
    assert all(item["isDemo"] for item in sessions)
    assert {item["sport"]["id"] for item in sessions} >= {
        "pickleball",
        "badminton",
        "basketball",
        "bowling",
        "yoga",
        "running",
        "cycling",
        "golf",
    }
    starts = [item["startAt"] for item in sessions]
    assert starts == sorted(starts)
    assert sessions[0]["title"] == "Demo Live Queue" and sessions[0]["status"] == "live"


def test_the_original_three_sessions_are_still_there(client):
    titles = {item["title"] for item in client.get(f"{API}/sessions").json()}
    assert {"Saturday Sunrise Rally", "After Work Smash", "Midweek Dink and Drink"} <= titles


def test_sessions_describe_themselves_per_sport(client):
    run = find(client, "Sunday Long Run")
    assert run["facility"] is None and run["kindLabel"] == "Group run"
    assert run["routeName"] == "Demo 10 km loop" and run["routeDistanceKm"] == 10.0
    assert run["queueMode"] == "none" and run["location"]["city"]["name"] == "Quezon City"
    hoops = find(client, "Saturday Hoops Run")
    assert hoops["teamFormatLabel"] == "5 v 5 full court" and hoops["queueMode"] == "winner_stays" and hoops["joinPolicy"] == "approval"
    assert hoops["facility"]["name"] == "Demo Hoops and Spikes Arena" and hoops["location"]["province"]["name"] == "Bulacan"
    assert find(client, "Morning Tee Time")["kind"] == "tee_time"


def test_filters(client):
    def titles(**params):
        return {item["title"] for item in client.get(f"{API}/sessions", params=params).json()}

    assert titles(sportId="pickleball") == {"Saturday Sunrise Rally", "Midweek Dink and Drink"}
    assert titles(category="fitness_activity") == {
        "Beginner Yoga Flow",
        "Open Mat",
        "Lap Swim Squad",
        "Sunday Long Run",
        "Weekend Gravel Ride",
    }
    assert titles(kind="group_activity") == {"Sunday Long Run", "Weekend Gravel Ride"}
    assert titles(regionCode="030000000") == {"Saturday Hoops Run", "Volleyball Night", "Friday Bowling Social"}
    assert titles(provinceCode="031400000") == {"Saturday Hoops Run", "Volleyball Night"}
    assert titles(cityCode="112402000") == {"Morning Tee Time"}
    assert titles(facilityId=facility_named("Demo Strike and Cue Lounge").id) == {"Friday Bowling Social"}
    assert titles(free=True) == {"Sunday Long Run", "Weekend Gravel Ride", "Demo Live Queue"}
    assert "After Work Smash" not in titles(hasSpots=True) and "After Work Smash" in titles()
    assert titles(q="tee") == {"Morning Tee Time"}
    assert titles(skillLevel="Beginner") >= {"Beginner Yoga Flow", "Sunday Long Run"}
    assert "Saturday Sunrise Rally" not in titles(skillLevel="Beginner")
    soon = titles(startsBefore=iso(manila(2, 0)))
    assert "Saturday Sunrise Rally" in soon and "Morning Tee Time" not in soon


def test_nearby_sessions_include_route_based_ones(client):
    response = client.get(f"{API}/sessions", params={"lat": 14.6760, "lng": 121.0437, "radiusKm": 8})
    titles = {item["title"] for item in response.json()}
    assert "Sunday Long Run" in titles and "Saturday Sunrise Rally" in titles
    assert "Weekend Gravel Ride" not in titles
    assert all(item["distanceKm"] is not None and item["distanceKm"] <= 8 for item in response.json())
    assert client.get(f"{API}/sessions", params={"lat": 14.6}).status_code == 422


def test_session_detail_shows_people_without_private_data(client):
    session = find(client, "After Work Smash")
    response = client.get(f"{API}/sessions/{session['id']}")
    body = response.json()
    assert [item["status"] for item in body["participants"]].count("confirmed") == 8
    assert body["participants"][-1]["status"] == "waitlisted" and body["participants"][-1]["waitlistPosition"] == 1
    assert "@" not in response.text and "email" not in response.text
    assert client.get(f"{API}/sessions/nope").status_code == 404


# --- joining and leaving ------------------------------------------------------


def test_joining_needs_an_account(client):
    session = find(client, "Midweek Dink and Drink")
    assert client.post(f"{API}/sessions/{session['id']}/join").status_code == 401


def test_join_and_leave(client, player):
    session = find(client, "Midweek Dink and Drink")
    assert session["joined"] == 3 and session["viewer"]["status"] is None
    joined = client.post(f"{API}/sessions/{session['id']}/join", headers=player).json()
    assert joined["joined"] == 4 and joined["spotsLeft"] == 8 and joined["viewer"]["status"] == "confirmed"
    # Joining twice changes nothing.
    assert client.post(f"{API}/sessions/{session['id']}/join", headers=player).json()["joined"] == 4
    left = client.post(f"{API}/sessions/{session['id']}/leave", headers=player).json()
    assert left["joined"] == 3 and left["viewer"]["status"] is None
    assert client.post(f"{API}/sessions/{session['id']}/leave", headers=player).status_code == 409
    # Rejoining after leaving works.
    assert client.post(f"{API}/sessions/{session['id']}/join", headers=player).json()["viewer"]["status"] == "confirmed"


def test_joined_state_is_per_player(client, player):
    """Audit item 1: the MVP shared one joined flag between every visitor."""
    session = find(client, "Midweek Dink and Drink")
    client.post(f"{API}/sessions/{session['id']}/join", headers=player)
    _, other = new_user("Someone Else")
    assert find(client, "Midweek Dink and Drink", other)["viewer"]["status"] is None
    assert find(client, "Midweek Dink and Drink", player)["viewer"]["status"] == "confirmed"
    assert find(client, "Midweek Dink and Drink")["viewer"]["status"] is None


def test_full_session_waitlists_and_promotes_in_order(client, player, db):
    """Audit item 2: leaving a full session must free the place for the first player waiting."""
    session = find(client, "After Work Smash")
    assert session["joined"] == session["capacity"] == 8 and session["waitlist"] == 1
    mine = client.post(f"{API}/sessions/{session['id']}/join", headers=player).json()
    assert mine["viewer"]["status"] == "waitlisted" and mine["viewer"]["waitlistPosition"] == 2
    assert mine["joined"] == 8 and mine["waitlist"] == 2

    confirmed = db.scalars(
        select(User.email)
        .join(SessionParticipant, SessionParticipant.user_id == User.id)
        .where(SessionParticipant.session_id == session["id"], SessionParticipant.status == "confirmed")
    ).all()
    db.rollback()
    first, second = confirmed[0], confirmed[1]

    after_first = client.post(f"{API}/sessions/{session['id']}/leave", headers=headers_for(first)).json()
    assert after_first["joined"] == 8 and after_first["waitlist"] == 1  # the earlier waitlisted player took the place
    assert find(client, "After Work Smash", player)["viewer"]["waitlistPosition"] == 1

    client.post(f"{API}/sessions/{session['id']}/leave", headers=headers_for(second))
    promoted = find(client, "After Work Smash", player)
    assert promoted["viewer"]["status"] == "confirmed" and promoted["joined"] == 8 and promoted["waitlist"] == 0
    me = scalar(select(User.id).where(User.email == "demo.player@courtmate.demo"))
    notice = scalar(select(Notification).where(Notification.user_id == me, Notification.kind == "waitlist_promoted"))
    assert notice is not None and "After Work Smash" in notice.body


def test_leaving_the_waitlist_does_not_free_a_confirmed_place(client, player):
    session = find(client, "After Work Smash")
    client.post(f"{API}/sessions/{session['id']}/join", headers=player)
    left = client.post(f"{API}/sessions/{session['id']}/leave", headers=player).json()
    assert left["joined"] == 8 and left["waitlist"] == 1


def test_concurrent_joins_never_overfill(client, db_path):
    """Audit item 3: twenty players race for four places."""
    _, host = new_user("Race Host")
    [session] = host_session(client, host, capacity=4, hostPlays=False).json()
    user_ids = [new_user(f"Joiner {index}")[0] for index in range(20)]
    barrier = threading.Barrier(len(user_ids))
    statuses: list[str] = []
    lock = threading.Lock()

    def attempt(user_id: str) -> None:
        barrier.wait()
        with database.session_factory()() as session_db:
            record = session_db.get(PlaySession, session["id"])
            participant = service.join(session_db, record, session_db.get(User, user_id))
            session_db.commit()
            with lock:
                statuses.append(participant.status)

    threads = [threading.Thread(target=attempt, args=(user_id,)) for user_id in user_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert statuses.count("confirmed") == 4 and statuses.count("waitlisted") == 16
    assert scalar(select(PlaySession.confirmed_count).where(PlaySession.id == session["id"])) == 4


# --- approvals and host controls ---------------------------------------------


def test_approval_sessions_hold_requests_for_the_host(client, player):
    session = find(client, "Saturday Hoops Run")
    host = headers_for("demo.p04@courtmate.demo")
    requested = client.post(f"{API}/sessions/{session['id']}/join", headers=player).json()
    assert requested["viewer"]["status"] == "pending" and requested["joined"] == 6
    assert requested["pending"] == 0  # hidden from players
    assert all(item["status"] != "pending" for item in requested["participants"])

    as_host = client.get(f"{API}/sessions/{session['id']}", headers=host).json()
    assert as_host["viewer"]["isHost"] and as_host["pending"] == 1
    pending = next(item for item in as_host["participants"] if item["status"] == "pending")

    stranger = new_user("Not The Host")[1]
    url = f"{API}/sessions/{session['id']}/participants/{pending['id']}"
    assert client.post(f"{url}/approve", headers=stranger).status_code == 403
    assert client.post(f"{url}/approve", headers=player).status_code == 403
    approved = client.post(f"{url}/approve", headers=host).json()
    assert approved["joined"] == 7 and approved["pending"] == 0
    assert find(client, "Saturday Hoops Run", player)["viewer"]["status"] == "confirmed"
    assert client.post(f"{url}/approve", headers=host).status_code == 409


def test_declined_and_removed_players_cannot_rejoin(client, player):
    session = find(client, "Saturday Hoops Run")
    host = headers_for("demo.p04@courtmate.demo")
    client.post(f"{API}/sessions/{session['id']}/join", headers=player)
    pending = next(
        item for item in client.get(f"{API}/sessions/{session['id']}", headers=host).json()["participants"] if item["status"] == "pending"
    )
    assert client.post(f"{API}/sessions/{session['id']}/participants/{pending['id']}/decline", headers=host).status_code == 200
    assert client.post(f"{API}/sessions/{session['id']}/join", headers=player).status_code == 403

    other = find(client, "Midweek Dink and Drink")
    other_host = headers_for("demo.p03@courtmate.demo")
    mine = client.post(f"{API}/sessions/{other['id']}/join", headers=player).json()
    me = next(item for item in mine["participants"] if item["user"]["displayName"] == "Demo Player")
    removed = client.post(f"{API}/sessions/{other['id']}/participants/{me['id']}/remove", headers=other_host).json()
    assert removed["joined"] == 3
    assert client.post(f"{API}/sessions/{other['id']}/join", headers=player).status_code == 403


# --- hosting ------------------------------------------------------------------


def test_host_a_session_at_a_facility(client, player):
    response = host_session(client, player, queueMode="rotation", courtsInPlay=2, feeCentavos=15000)
    assert response.status_code == 201, response.text
    [session] = response.json()
    assert session["venueName"] == RALLY and session["location"]["city"]["name"] == "Quezon City"
    assert session["viewer"] == {"status": "confirmed", "isHost": True, "waitlistPosition": None, "checkedIn": False, "queueState": "idle"}
    assert session["joined"] == 1 and session["isDemo"] is False and session["hasVenueBooking"] is False
    assert find(client, "Test Rally")["id"] == session["id"]


def test_host_a_route_based_session_without_a_facility(client, player):
    start = manila(3, 5, 30)
    payload = {
        "title": "Dawn Patrol 12K",
        "sportId": "running",
        "kind": "group_activity",
        "startAt": iso(start),
        "endAt": iso(start + dt.timedelta(minutes=90)),
        "capacity": 30,
        "cityCode": "031410000",
        "barangayCode": "031410012",
        "venueName": "Capitol grounds main gate",
        "routeName": "River loop",
        "routeDistanceKm": 12,
        "latitude": 14.8433,
        "longitude": 120.8114,
    }
    response = client.post(f"{API}/sessions", headers=player, json=payload)
    assert response.status_code == 201, response.text
    [session] = response.json()
    assert session["facility"] is None and session["location"]["barangay"]["name"] == "Bulihan"
    assert session["location"]["province"]["name"] == "Bulacan" and session["routeDistanceKm"] == 12
    assert session["startAt"].endswith("T21:30:00Z")  # 05:30 in Manila


def test_sessions_follow_each_sports_rules(client, player):
    def detail(**overrides):
        response = host_session(client, player, **overrides)
        assert response.status_code == 422, response.text
        return str(response.json()["detail"])

    assert "kind of session" in detail(kind="tee_time")
    assert "skill levels" in detail(skillLevel="White belt")
    assert "not played in that format" in detail(teamFormat="5v5")
    arena = facility_named("Demo Aquatic and Fitness Club").id
    assert "do not use that queue" in detail(sportId="yoga", kind="class", teamFormat="", facilityId=arena, queueMode="rotation")
    assert "not set up for" in detail(sportId="bowling", teamFormat="")
    assert "future" in detail(start=manila(-1, 10))
    assert "Choose a facility" in detail(facilityId=None)
    assert "Unknown sport" in detail(sportId="quidditch")
    assert "minPlayers" in detail(minPlayers=9)
    assert host_session(client, {}).status_code == 401


def test_hosting_can_reserve_the_venue_in_the_same_step(client, player):
    court = resource_named(RALLY, "Pickleball Court 3")
    [session] = host_session(client, player, resourceId=court.id).json()
    assert session["hasVenueBooking"] is True
    [reservation] = client.get(f"{API}/reservations", headers=player).json()
    assert reservation["resource"]["name"] == "Pickleball Court 3" and reservation["note"] == "Session: Test Rally"

    # The court is now taken, so a second session cannot reserve it and is not created at all.
    _, rival = new_user("Rival Host")
    clash = host_session(client, rival, resourceId=court.id, title="Rival Rally")
    assert clash.status_code == 409
    assert "Rival Rally" not in {item["title"] for item in client.get(f"{API}/sessions").json()}

    # Cancelling the session gives the court back.
    cancelled = client.post(f"{API}/sessions/{session['id']}/cancel", headers=player, json={"reason": "Rain"}).json()
    assert cancelled["status"] == "cancelled" and cancelled["cancelReason"] == "Rain"
    assert scalar(select(Reservation.status).where(Reservation.id == reservation["id"])) == "cancelled"
    assert host_session(client, rival, resourceId=court.id, title="Rival Rally").status_code == 201


def test_weekly_series(client, player):
    response = host_session(client, player, repeatWeeks=3)
    sessions = response.json()
    assert len(sessions) == 3 and len({item["seriesId"] for item in sessions}) == 1
    starts = [dt.datetime.fromisoformat(item["startAt"]) for item in sessions]
    assert starts[1] - starts[0] == starts[2] - starts[1] == dt.timedelta(weeks=1)


def test_only_the_host_can_manage(client, player):
    [session] = host_session(client, player).json()
    stranger = new_user("Not The Host")[1]
    for action in ("start", "complete", "cancel"):
        assert client.post(f"{API}/sessions/{session['id']}/{action}", headers=stranger).status_code == 403
    assert client.patch(f"{API}/sessions/{session['id']}", headers=stranger, json={"title": "Hijacked"}).status_code == 403
    assert client.post(f"{API}/sessions/{session['id']}/queue/next", headers=stranger).status_code == 403


def test_raising_the_limit_lets_the_waitlist_in(client, player):
    [session] = host_session(client, player, capacity=2).json()
    joiners = [new_user(f"Joiner {index}")[1] for index in range(3)]
    for headers in joiners:
        client.post(f"{API}/sessions/{session['id']}/join", headers=headers)
    before = client.get(f"{API}/sessions/{session['id']}").json()
    assert before["joined"] == 2 and before["waitlist"] == 2

    assert client.patch(f"{API}/sessions/{session['id']}", headers=player, json={"capacity": 1}).status_code == 409
    after = client.patch(f"{API}/sessions/{session['id']}", headers=player, json={"capacity": 3}).json()
    assert after["capacity"] == 3 and after["joined"] == 3 and after["waitlist"] == 1
    assert find(client, "Test Rally", joiners[1])["viewer"]["status"] == "confirmed"
    assert find(client, "Test Rally", joiners[2])["viewer"]["waitlistPosition"] == 1


def test_rescheduling_tells_the_players(client, player):
    [session] = host_session(client, player).json()
    joiner_id, joiner = new_user("Early Bird")
    client.post(f"{API}/sessions/{session['id']}/join", headers=joiner)
    start = manila(4, 16)
    moved = client.patch(
        f"{API}/sessions/{session['id']}", headers=player, json={"startAt": iso(start), "endAt": iso(start + dt.timedelta(hours=2))}
    )
    assert moved.status_code == 200 and moved.json()["startAt"].endswith("T08:00:00Z")
    assert (
        scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == joiner_id, Notification.kind == "session_rescheduled")
        )
        == 1
    )

    court = resource_named(RALLY, "Pickleball Court 4")
    [booked] = host_session(client, player, resourceId=court.id, title="With Court", start=manila(5, 10)).json()
    locked = client.patch(
        f"{API}/sessions/{booked['id']}", headers=player, json={"startAt": iso(start), "endAt": iso(start + dt.timedelta(hours=2))}
    )
    assert locked.status_code == 409 and "venue booking" in locked.json()["detail"]


def test_cancelled_sessions_leave_discovery_and_notify(client, player):
    [session] = host_session(client, player).json()
    joiner_id, joiner = new_user("Early Bird")
    client.post(f"{API}/sessions/{session['id']}/join", headers=joiner)
    client.post(f"{API}/sessions/{session['id']}/cancel", headers=player, json={"reason": "Court flooded"})
    assert "Test Rally" not in {item["title"] for item in client.get(f"{API}/sessions").json()}
    notice = scalar(select(Notification).where(Notification.user_id == joiner_id, Notification.kind == "session_cancelled"))
    assert "Court flooded" in notice.body
    assert client.post(f"{API}/sessions/{session['id']}/join", headers=new_user("Late Comer")[1]).status_code == 409
    assert client.post(f"{API}/sessions/{session['id']}/cancel", headers=player).status_code == 409


def test_my_sessions(client, player):
    assert client.get(f"{API}/sessions/mine").status_code == 401
    seeded = {item["title"] for item in client.get(f"{API}/sessions/mine", headers=player).json()}
    assert seeded == {"Demo Live Queue"}
    [hosted] = host_session(client, player).json()
    client.post(f"{API}/sessions/{find(client, 'Friday Bowling Social')['id']}/join", headers=player)
    playing = [item["title"] for item in client.get(f"{API}/sessions/mine", headers=player).json()]
    assert set(playing) == {"Demo Live Queue", "Test Rally", "Friday Bowling Social"}
    hosting = client.get(f"{API}/sessions/mine", headers=player, params={"role": "hosting"}).json()
    assert [item["id"] for item in hosting] == [hosted["id"]]
    client.post(f"{API}/sessions/{hosted['id']}/cancel", headers=player)
    past = client.get(f"{API}/sessions/mine", headers=player, params={"role": "hosting", "scope": "past"}).json()
    assert [item["status"] for item in past] == ["cancelled"]


def test_demo_sessions_are_renewed_when_they_run_out(db):
    from app import seed

    assert seed.refresh_demo_sessions(db) is False  # plenty of upcoming demo sessions
    later = dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
    assert seed.refresh_demo_sessions(db, now=later) is True
    upcoming = db.scalar(
        select(func.count())
        .select_from(PlaySession)
        .where(PlaySession.is_demo.is_(True), PlaySession.status == "scheduled", PlaySession.end_at > later)
    )
    assert upcoming == 13
    assert db.scalar(select(func.count()).select_from(PlaySession).where(PlaySession.status == "live")) == 1
    db.rollback()
    assert demo_headers  # imported for other tests
