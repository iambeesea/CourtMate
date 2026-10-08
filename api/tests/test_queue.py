import datetime as dt

from sqlalchemy import select

from app.models import PlaySession, SessionParticipant

from .conftest import API, facility_named, iso, manila, new_user, scalar


def live_session(client, headers, players=8, **overrides):
    """Host a doubles session, fill it, start it, and check everyone in. Returns (session, [(name, headers)])."""
    start = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    payload = {
        "title": "Queue Night",
        "sportId": "badminton",
        "kind": "open_play",
        "startAt": iso(start),
        "endAt": iso(start + dt.timedelta(hours=3)),
        "capacity": 12,
        "teamFormat": "doubles",
        "queueMode": "rotation",
        "courtsInPlay": 2,
        "hostPlays": False,
        "facilityId": facility_named("Demo Rally Center").id,
        **overrides,
    }
    response = client.post(f"{API}/sessions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    [session] = response.json()
    people = []
    for index in range(players):
        name = f"Queue Player {index + 1:02d}"
        _, player_headers = new_user(name)
        client.post(f"{API}/sessions/{session['id']}/join", headers=player_headers)
        people.append((name, player_headers))
    assert client.post(f"{API}/sessions/{session['id']}/start", headers=headers).status_code == 200
    for _, player_headers in people:
        assert client.post(f"{API}/sessions/{session['id']}/check-in", headers=player_headers).status_code == 200
    return session, people


def names(entries):
    return [entry["user"]["displayName"] for entry in entries]


def test_seeded_live_queue_is_visible_to_everyone(client, player):
    session = next(item for item in client.get(f"{API}/sessions").json() if item["title"] == "Demo Live Queue")
    queue = client.get(f"{API}/sessions/{session['id']}/queue").json()
    assert queue["mode"] == "rotation" and queue["playersPerMatch"] == 4 and queue["status"] == "live"
    assert queue["courts"][0]["match"]["status"] == "in_progress" and queue["courts"][1]["match"] is None
    assert len(queue["courts"][0]["match"]["players"]) == 4
    assert len(queue["waiting"]) == 3 and names(queue["notCheckedIn"]) == ["Demo Player"]
    assert queue["canManage"] is False

    mine = client.post(f"{API}/sessions/{session['id']}/check-in", headers=player).json()
    assert names(mine["waiting"])[-1] == "Demo Player" and mine["notCheckedIn"] == []


def test_check_in_waits_for_the_host_to_start(client, player):
    start = manila(0, 0) + dt.timedelta(days=1, hours=10)
    payload = {
        "title": "Not Yet",
        "sportId": "badminton",
        "startAt": iso(start),
        "endAt": iso(start + dt.timedelta(hours=2)),
        "capacity": 8,
        "teamFormat": "doubles",
        "queueMode": "rotation",
        "facilityId": facility_named("Demo Rally Center").id,
    }
    [session] = client.post(f"{API}/sessions", headers=player, json=payload).json()
    assert "host starts" in client.post(f"{API}/sessions/{session['id']}/check-in", headers=player).json()["detail"]
    assert "two hours" in client.post(f"{API}/sessions/{session['id']}/start", headers=player).json()["detail"]
    assert "not started" in client.post(f"{API}/sessions/{session['id']}/queue/next", headers=player).json()["detail"]


def test_rotation_queue(client, player):
    session, people = live_session(client, player)
    url = f"{API}/sessions/{session['id']}"
    queue = client.get(f"{url}/queue", headers=player).json()
    assert names(queue["waiting"]) == [name for name, _ in people] and queue["canManage"] is True

    first = client.post(f"{url}/queue/next", headers=player).json()
    court_one = first["courts"][0]["match"]
    assert [p["user"]["displayName"] for p in court_one["players"] if p["side"] == 1] == ["Queue Player 01", "Queue Player 02"]
    assert [p["user"]["displayName"] for p in court_one["players"] if p["side"] == 2] == ["Queue Player 03", "Queue Player 04"]
    assert names(first["waiting"]) == ["Queue Player 05", "Queue Player 06", "Queue Player 07", "Queue Player 08"]

    second = client.post(f"{url}/queue/next", headers=player).json()
    assert second["courts"][1]["match"]["courtLabel"] == "Court 2" and second["waiting"] == []
    assert "Every court is in use" in client.post(f"{url}/queue/next", headers=player).json()["detail"]

    # A player in the match records the score; everyone on that court goes to the back of the queue.
    result = client.post(f"{API}/matches/{court_one['id']}/result", headers=people[0][1], json={"games": [[21, 15], [18, 21], [21, 19]]})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "completed" and body["winnerSide"] == 1 and body["score"]["totals"] == [2, 1]
    after = client.get(f"{url}/queue").json()
    assert after["courts"][0]["match"] is None
    assert names(after["waiting"]) == ["Queue Player 01", "Queue Player 02", "Queue Player 03", "Queue Player 04"]
    assert all(entry["gamesPlayed"] == 1 for entry in after["waiting"])
    assert "4 players need to be waiting" not in client.post(f"{url}/queue/next", headers=player).text

    history = client.get(f"{url}/matches").json()
    assert [item["status"] for item in history].count("completed") == 1
    assert client.post(f"{API}/matches/{court_one['id']}/result", headers=player, json={"games": [[21, 0], [21, 0]]}).status_code == 409


def test_not_enough_players_waiting(client, player):
    session, _ = live_session(client, player, players=3)
    response = client.post(f"{API}/sessions/{session['id']}/queue/next", headers=player)
    assert response.status_code == 409 and "4 players need to be waiting; 3 are" in response.json()["detail"]


def test_scores_follow_the_sports_rules(client, player):
    session, people = live_session(client, player, players=4)
    match = client.post(f"{API}/sessions/{session['id']}/queue/next", headers=player).json()["courts"][0]["match"]
    url = f"{API}/matches/{match['id']}/result"

    def rejected(payload):
        response = client.post(url, headers=player, json=payload)
        assert response.status_code == 422, response.text
        return str(response.json()["detail"])

    assert "needs a winner" in rejected({"games": [[21, 15], [15, 21]]})
    assert "cannot end level" in rejected({"games": [[21, 21]]})
    assert "best of 3" in rejected({"games": [[21, 1], [1, 21], [21, 1], [21, 1]]})
    assert "Enter the score of each game" in rejected({"totals": [2, 1]})
    assert "between 0 and" in rejected({"games": [[-1, 21]]})
    assert "does not track" in rejected({"games": [[21, 10], [21, 10]], "playerStats": {match["players"][0]["user"]["id"]: {"aces": 3}}})
    assert client.post(url, headers=new_user("Bystander")[1], json={"games": [[21, 10], [21, 10]]}).status_code == 403
    assert client.post(url, headers=people[3][1], json={"games": [[10, 21], [12, 21]]}).json()["winnerSide"] == 2


def test_winner_stays_keeps_the_winners_on_court(client, player):
    session, people = live_session(
        client,
        player,
        players=6,
        sportId="basketball",
        kind="pickup_game",
        teamFormat="3x3",
        queueMode="winner_stays",
        courtsInPlay=1,
        facilityId=facility_named("Demo Hoops and Spikes Arena").id,
    )
    url = f"{API}/sessions/{session['id']}"
    for index in range(3):
        _, extra = new_user(f"Queue Player {index + 7:02d}")
        client.post(f"{url}/join", headers=extra)
        client.post(f"{url}/check-in", headers=extra)

    match = client.post(f"{url}/queue/next", headers=player).json()["courts"][0]["match"]
    assert len(match["players"]) == 6
    scorer = match["players"][3]["user"]["id"]  # a player on side 2
    result = client.post(
        f"{API}/matches/{match['id']}/result",
        headers=player,
        json={"totals": [15, 21], "playerStats": {scorer: {"points": 9, "rebounds": 4, "assists": 2}}},
    ).json()
    assert result["winnerSide"] == 2 and result["score"] == {"totals": [15, 21]}
    assert next(p for p in result["players"] if p["user"]["id"] == scorer)["stats"] == {"points": 9, "rebounds": 4, "assists": 2}

    waiting = names(client.get(f"{url}/queue").json()["waiting"])
    # Winners (players 04–06) stay at the front, the next challengers follow, the losers go to the back.
    assert waiting[:3] == ["Queue Player 04", "Queue Player 05", "Queue Player 06"]
    assert waiting[3:6] == ["Queue Player 07", "Queue Player 08", "Queue Player 09"]
    assert waiting[6:] == ["Queue Player 01", "Queue Player 02", "Queue Player 03"]

    rematch = client.post(f"{url}/queue/next", headers=player).json()["courts"][0]["match"]
    assert sorted(p["user"]["displayName"] for p in rematch["players"] if p["side"] == 1) == [
        "Queue Player 04",
        "Queue Player 05",
        "Queue Player 06",
    ]


def test_resting_and_rejoining(client, player):
    session, people = live_session(client, player, players=5)
    url = f"{API}/sessions/{session['id']}"
    rested = client.post(f"{url}/queue/me", headers=people[0][1], json={"state": "idle"}).json()
    assert names(rested["resting"]) == ["Queue Player 01"] and "Queue Player 01" not in names(rested["waiting"])
    back = client.post(f"{url}/queue/me", headers=people[0][1], json={"state": "waiting"}).json()
    assert names(back["waiting"])[-1] == "Queue Player 01"

    match = client.post(f"{url}/queue/next", headers=player).json()["courts"][0]["match"]
    on_court = next(headers for name, headers in people if name == match["players"][0]["user"]["displayName"])
    assert "on court" in client.post(f"{url}/queue/me", headers=on_court, json={"state": "idle"}).json()["detail"]
    assert "Finish your current match" in client.post(f"{url}/leave", headers=on_court).json()["detail"]


def test_voiding_a_match_restores_the_queue(client, player):
    session, people = live_session(client, player, players=6)
    url = f"{API}/sessions/{session['id']}"
    match = client.post(f"{url}/queue/next", headers=player).json()["courts"][0]["match"]
    assert client.post(f"{API}/matches/{match['id']}/void", headers=people[0][1]).status_code == 403
    assert client.post(f"{API}/matches/{match['id']}/void", headers=player).json()["status"] == "void"
    queue = client.get(f"{url}/queue").json()
    assert names(queue["waiting"]) == [name for name, _ in people]
    assert all(entry["gamesPlayed"] == 0 for entry in queue["waiting"])
    assert client.get(f"{url}/matches").json() == []


def test_finishing_the_session_closes_the_queue(client, player):
    session, _ = live_session(client, player, players=5)
    url = f"{API}/sessions/{session['id']}"
    client.post(f"{url}/queue/next", headers=player)
    done = client.post(f"{url}/complete", headers=player).json()
    assert done["status"] == "completed"
    states = scalar(select(SessionParticipant.queue_state).where(SessionParticipant.session_id == session["id"]).distinct())
    assert states == "idle"
    assert scalar(select(PlaySession.status).where(PlaySession.id == session["id"])) == "completed"
    assert client.get(f"{url}/matches").json() == []
    assert client.post(f"{url}/queue/next", headers=player).status_code == 409


def test_sessions_without_a_queue_reject_queue_calls(client, player):
    session, people = live_session(client, player, players=2, queueMode="none")
    url = f"{API}/sessions/{session['id']}"
    assert "does not run a queue" in client.post(f"{url}/queue/next", headers=player).json()["detail"]
    queue = client.get(f"{url}/queue").json()
    assert queue["mode"] == "none" and queue["waiting"] == [] and len(queue["resting"]) == 2
