import datetime as dt

from sqlalchemy import select

from app.models import PlaySession

from .conftest import API, facility_named, iso, new_user, scalar
from .test_queue import live_session


def stat(body, key):
    return next(item for item in body["summary"] if item["key"] == key)


def test_records_need_sign_in(client):
    for path in ("records", "stats", "matches", "achievements", "activities"):
        assert client.get(f"{API}/players/me/{path}").status_code == 401


def test_a_new_player_has_no_figures_at_all(client):
    """Nothing is invented: no results means no numbers."""
    _, fresh = new_user("Brand New")
    assert client.get(f"{API}/players/me/records", headers=fresh).json() == []
    for sport in ("pickleball", "running", "yoga"):
        body = client.get(f"{API}/players/me/stats", headers=fresh, params={"sportId": sport}).json()
        assert body["hasData"] is False and body["summary"] == [] and body["recentForm"] == []
        assert body["streak"] == 0 and body["partners"] == [] and all(month["count"] == 0 for month in body["byMonth"])
    assert client.get(f"{API}/players/me/matches", headers=fresh).json() == []
    assert client.get(f"{API}/players/me/achievements", headers=fresh).json() == []


def test_overview_lists_sports_with_results(client, player):
    records = client.get(f"{API}/players/me/records", headers=player).json()
    assert [(item["sport"]["id"], item["recordType"], item["entries"]) for item in records] == [
        ("pickleball", "matches", 28),
        ("badminton", "matches", 6),
        ("running", "activities", 5),
        ("bowling", "activities", 4),
    ]


def test_match_record_is_computed_from_recorded_matches(client, player):
    body = client.get(f"{API}/players/me/stats", headers=player, params={"sportId": "pickleball"}).json()
    assert body["recordType"] == "matches" and body["hasData"] and body["containsDemoData"]
    assert stat(body, "matches")["value"] == 28 and stat(body, "wins")["value"] == 18 and stat(body, "losses")["value"] == 10
    assert stat(body, "win_rate")["display"] == "64%" and stat(body, "wins")["note"] == "64% win rate"
    assert body["recentForm"] == ["L", "W", "W", "W", "W"]
    assert body["streakType"] == "W" and body["streak"] == 4 and body["bestWinStreak"] == 4
    assert stat(body, "games_won")["label"] == "Games won"
    assert sum(month["count"] for month in body["byMonth"]) <= 28 and len(body["byMonth"]) == 6
    assert body["partners"][0]["user"]["displayName"] == "Player 01" and body["partners"][0]["matches"] == 21
    assert "draws" not in {item["key"] for item in body["summary"]}
    # Without a sport, the most active sport is returned.
    assert client.get(f"{API}/players/me/stats", headers=player).json()["sport"]["id"] == "pickleball"


def test_match_history(client, player):
    matches = client.get(f"{API}/players/me/matches", headers=player, params={"sportId": "pickleball", "limit": 5}).json()
    assert [item["result"] for item in matches] == ["W", "W", "W", "W", "L"]  # newest first
    assert matches[0]["mySide"] == 1 and matches[0]["score"]["totals"][0] == 2 and matches[0]["isDemo"]
    assert len(client.get(f"{API}/players/me/matches", headers=player, params={"sportId": "badminton"}).json()) == 6


def test_activity_records_use_each_sports_own_aggregations(client, player):
    running = client.get(f"{API}/players/me/stats", headers=player, params={"sportId": "running"}).json()
    assert running["recordType"] == "activities" and running["recentForm"] == []
    assert stat(running, "activities")["value"] == 5
    assert stat(running, "distance")["display"] == "50.7" and stat(running, "distance")["unit"] == "km"
    assert stat(running, "longest")["display"] == "21.1"
    assert stat(running, "pace")["display"] == "6:04" and stat(running, "pace")["unit"] == "min/km"  # 308 min over 50.7 km

    bowling = client.get(f"{API}/players/me/stats", headers=player, params={"sportId": "bowling"}).json()
    assert stat(bowling, "games")["value"] == 4 and stat(bowling, "best")["value"] == 171 and stat(bowling, "average")["display"] == "152"


def test_log_an_activity(client):
    _, runner = new_user("Fresh Runner")
    when = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    created = client.post(
        f"{API}/players/me/activities",
        headers=runner,
        json={"sportId": "running", "occurredAt": iso(when), "metrics": {"distance_km": 10, "duration_min": 55}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "self_reported" and created.json()["isDemo"] is False
    body = client.get(f"{API}/players/me/stats", headers=runner, params={"sportId": "running"}).json()
    assert stat(body, "pace")["display"] == "5:30" and body["containsDemoData"] is False
    assert [item["id"] for item in client.get(f"{API}/players/me/activities", headers=runner).json()] == [created.json()["id"]]

    assert client.delete(f"{API}/players/me/activities/{created.json()['id']}", headers=new_user("Someone Else")[1]).status_code == 404
    assert client.delete(f"{API}/players/me/activities/{created.json()['id']}", headers=runner).status_code == 204
    assert client.get(f"{API}/players/me/stats", headers=runner, params={"sportId": "running"}).json()["hasData"] is False


def test_activity_validation_follows_the_sport(client, player):
    now = dt.datetime.now(dt.UTC)

    def rejected(sport, metrics, when=None):
        response = client.post(
            f"{API}/players/me/activities",
            headers=player,
            json={"sportId": sport, "occurredAt": iso(when or now - dt.timedelta(hours=1)), "metrics": metrics},
        )
        assert response.status_code == 422, response.text
        return str(response.json()["detail"])

    assert "Duration is required" in rejected("running", {"distance_km": 5})
    assert "does not track: score" in rejected("running", {"distance_km": 5, "duration_min": 30, "score": 200})
    assert "between 0 and 300" in rejected("bowling", {"score": 301})
    assert "whole number" in rejected("bowling", {"score": 150.5})
    assert "before it happens" in rejected("running", {"distance_km": 5, "duration_min": 30}, now + dt.timedelta(days=1))
    assert "matches or attendance" in rejected("badminton", {"score": 21})
    assert "matches or attendance" in rejected("yoga", {"minutes": 60})
    # Swimming's duration is optional.
    ok = client.post(
        f"{API}/players/me/activities",
        headers=player,
        json={"sportId": "swimming", "occurredAt": iso(now - dt.timedelta(hours=1)), "metrics": {"distance_m": 1500}},
    )
    assert ok.status_code == 201


def test_results_recorded_in_a_session_feed_every_players_record(client, player):
    session, people = live_session(client, player, players=4)
    match = client.post(f"{API}/sessions/{session['id']}/queue/next", headers=player).json()["courts"][0]["match"]
    client.post(f"{API}/matches/{match['id']}/result", headers=player, json={"games": [[21, 12], [21, 16]]})
    winner = client.get(f"{API}/players/me/stats", headers=people[0][1], params={"sportId": "badminton"}).json()
    loser = client.get(f"{API}/players/me/stats", headers=people[3][1], params={"sportId": "badminton"}).json()
    assert stat(winner, "wins")["value"] == 1 and winner["recentForm"] == ["W"] and winner["containsDemoData"] is False
    assert stat(loser, "losses")["value"] == 1 and loser["streakType"] == "L"
    assert winner["partners"][0]["user"]["displayName"] == "Queue Player 02" and winner["partners"][0]["wins"] == 1
    assert stat(winner, "games_won")["value"] == 2 and stat(winner, "games_won")["note"] == "0 lost"


def test_voided_matches_do_not_count(client, player):
    session, people = live_session(client, player, players=4)
    match = client.post(f"{API}/sessions/{session['id']}/queue/next", headers=player).json()["courts"][0]["match"]
    client.post(f"{API}/matches/{match['id']}/void", headers=player)
    assert client.get(f"{API}/players/me/stats", headers=people[0][1], params={"sportId": "badminton"}).json()["hasData"] is False


def test_basketball_counts_player_stats_only_where_recorded(client, player):
    session, people = live_session(
        client, player, players=6, sportId="basketball", kind="pickup_game", teamFormat="3x3", queueMode="winner_stays", courtsInPlay=1,
        facilityId=facility_named("Demo Hoops and Spikes Arena").id,
    )  # fmt: skip
    url = f"{API}/sessions/{session['id']}"
    match = client.post(f"{url}/queue/next", headers=player).json()["courts"][0]["match"]
    scorer = next(p["user"]["id"] for p in match["players"] if p["user"]["displayName"] == "Queue Player 01")
    client.post(
        f"{API}/matches/{match['id']}/result",
        headers=player,
        json={"totals": [21, 18], "playerStats": {scorer: {"points": 11, "assists": 3}}},
    )

    with_line = client.get(f"{API}/players/me/stats", headers=people[0][1], params={"sportId": "basketball"}).json()
    assert stat(with_line, "points")["value"] == 11 and stat(with_line, "assists")["value"] == 3
    assert "rebounds" not in {item["key"] for item in with_line["summary"]}  # nobody counted rebounds
    assert stat(with_line, "side_scored")["value"] == 21 and stat(with_line, "side_scored")["note"] == "18 conceded"
    without_line = client.get(f"{API}/players/me/stats", headers=people[1][1], params={"sportId": "basketball"}).json()
    assert stat(without_line, "wins")["value"] == 1
    assert "points" not in {item["key"] for item in without_line["summary"]}


def test_attendance_counts_checked_in_finished_sessions(client, player):
    start = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    payload = {
        "title": "Sunrise Flow",
        "sportId": "yoga",
        "kind": "class",
        "startAt": iso(start),
        "endAt": iso(start + dt.timedelta(minutes=90)),
        "capacity": 10,
        "hostPlays": False,
        "facilityId": facility_named("Demo Aquatic and Fitness Club").id,
    }
    [session] = client.post(f"{API}/sessions", headers=player, json=payload).json()
    _, came = new_user("Showed Up")
    _, skipped = new_user("Stayed Home")
    for headers in (came, skipped):
        client.post(f"{API}/sessions/{session['id']}/join", headers=headers)
    client.post(f"{API}/sessions/{session['id']}/start", headers=player)
    client.post(f"{API}/sessions/{session['id']}/check-in", headers=came)

    assert client.get(f"{API}/players/me/stats", headers=came, params={"sportId": "yoga"}).json()["hasData"] is False  # not finished yet
    client.post(f"{API}/sessions/{session['id']}/complete", headers=player)
    assert scalar(select(PlaySession.status).where(PlaySession.id == session["id"])) == "completed"

    attended = client.get(f"{API}/players/me/stats", headers=came, params={"sportId": "yoga"}).json()
    assert (
        attended["recordType"] == "attendance" and stat(attended, "sessions")["value"] == 1 and stat(attended, "hours")["display"] == "1.5"
    )
    assert client.get(f"{API}/players/me/stats", headers=skipped, params={"sportId": "yoga"}).json()["hasData"] is False
    assert [item["sport"]["id"] for item in client.get(f"{API}/players/me/records", headers=came).json()] == ["yoga"]


def test_achievements_come_from_real_records(client, player):
    earned = {item["id"]: item for item in client.get(f"{API}/players/me/achievements", headers=player).json()}
    assert set(earned) == {"first_result", "hot_streak", "regular", "multi_sport", "community_player"}
    assert earned["hot_streak"]["description"] == "Won 4 matches in a row."
    assert earned["multi_sport"]["description"] == "Records in 4 sports."


def test_notifications(client, player):
    assert client.get(f"{API}/notifications").status_code == 401
    assert client.get(f"{API}/notifications", headers=player).json() == {"unread": 0, "items": []}

    session = next(item for item in client.get(f"{API}/sessions").json() if item["title"] == "Saturday Hoops Run")
    client.post(f"{API}/sessions/{session['id']}/join", headers=player)
    from .conftest import headers_for

    host = headers_for("demo.p04@courtmate.demo")
    inbox = client.get(f"{API}/notifications", headers=host).json()
    assert inbox["unread"] == 1 and inbox["items"][0]["kind"] == "join_request"
    assert "Demo Player asked to join" in inbox["items"][0]["body"] and inbox["items"][0]["link"] == f"/sessions/{session['id']}"

    pending = next(
        p for p in client.get(f"{API}/sessions/{session['id']}", headers=host).json()["participants"] if p["status"] == "pending"
    )
    client.post(f"{API}/sessions/{session['id']}/participants/{pending['id']}/approve", headers=host)
    mine = client.get(f"{API}/notifications", headers=player).json()
    assert mine["unread"] == 1 and mine["items"][0]["title"] == "Request approved"

    # One player cannot read or clear another's notifications.
    assert client.post(f"{API}/notifications/read", headers=host, json={"ids": [mine["items"][0]["id"]]}).status_code == 204
    assert client.get(f"{API}/notifications", headers=player).json()["unread"] == 1
    assert client.post(f"{API}/notifications/read", headers=player).status_code == 204
    after = client.get(f"{API}/notifications", headers=player).json()
    assert after["unread"] == 0 and after["items"][0]["readAt"] is not None
