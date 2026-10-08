from .conftest import API, new_user

NEW = {
    "name": "Bulacan Badminton Barkada",
    "description": "Friday night doubles.",
    "cityCode": "031410000",
    "sportIds": ["badminton", "pickleball"],
}


def names(response):
    return [item["name"] for item in response.json()]


def test_demo_communities_keep_the_original_three(client):
    response = client.get(f"{API}/communities")
    assert {"Rally Community", "Shuttle Community", "Dink Community"} <= set(names(response))
    assert all(item["isDemo"] for item in response.json())
    rally = next(item for item in response.json() if item["name"] == "Rally Community")
    assert rally["memberCount"] == 7 and rally["sports"][0]["id"] == "pickleball" and rally["city"]["name"] == "Quezon City"
    assert rally["viewerRole"] is None


def test_filters(client, player):
    assert names(client.get(f"{API}/communities", params={"sportId": "basketball"})) == ["Demo Malolos Hoopers"]
    assert names(client.get(f"{API}/communities", params={"provinceCode": "031400000"})) == ["Demo Malolos Hoopers"]
    assert names(client.get(f"{API}/communities", params={"q": "dink"})) == ["Dink Community"]
    assert names(client.get(f"{API}/communities", params={"mine": True}, headers=player)) == ["Rally Community"]
    assert client.get(f"{API}/communities", params={"mine": True}).status_code == 401


def test_community_detail_lists_members_teams_and_no_private_data(client, player):
    hoopers = next(item for item in client.get(f"{API}/communities").json() if item["name"] == "Demo Malolos Hoopers")
    response = client.get(f"{API}/communities/{hoopers['id']}", headers=player)
    body = response.json()
    assert body["members"][0]["role"] == "owner" and len(body["members"]) == 6
    assert [team["name"] for team in body["teams"]] == ["Demo Hoopers Blue"]
    assert "@" not in response.text
    assert client.get(f"{API}/communities/{hoopers['slug']}").json()["id"] == hoopers["id"]
    assert client.get(f"{API}/communities/nope").status_code == 404


def test_create_join_and_leave(client, player):
    assert client.post(f"{API}/communities", json=NEW).status_code == 401
    created = client.post(f"{API}/communities", headers=player, json=NEW)
    assert created.status_code == 201, created.text
    community = created.json()
    assert community["viewerRole"] == "owner" and community["memberCount"] == 1 and community["isDemo"] is False
    assert community["city"]["name"] == "City of Malolos" and community["region"]["name"] == "Central Luzon"
    assert client.post(f"{API}/communities", headers=player, json=NEW).status_code == 409

    _, friend = new_user("New Friend")
    joined = client.post(f"{API}/communities/{community['id']}/join", headers=friend).json()
    assert joined["memberCount"] == 2 and joined["viewerRole"] == "member"
    assert client.post(f"{API}/communities/{community['id']}/join", headers=friend).json()["memberCount"] == 2
    assert client.post(f"{API}/communities/{community['id']}/leave", headers=friend).json()["memberCount"] == 1
    assert client.post(f"{API}/communities/{community['id']}/leave", headers=friend).status_code == 409
    assert "owner cannot leave" in client.post(f"{API}/communities/{community['id']}/leave", headers=player).json()["detail"]


def test_only_organisers_edit(client, player):
    community = client.post(f"{API}/communities", headers=player, json=NEW).json()
    _, friend = new_user("New Friend")
    client.post(f"{API}/communities/{community['id']}/join", headers=friend)
    assert client.patch(f"{API}/communities/{community['id']}", headers=friend, json={"name": "Hijacked"}).status_code == 403
    edited = client.patch(
        f"{API}/communities/{community['id']}", headers=player, json={"description": "Now with coffee.", "sportIds": ["badminton"]}
    )
    assert edited.status_code == 200 and edited.json()["description"] == "Now with coffee." and len(edited.json()["sports"]) == 1


def test_validation(client, player):
    assert client.post(f"{API}/communities", headers=player, json={**NEW, "sportIds": ["quidditch"]}).status_code == 422
    assert client.post(f"{API}/communities", headers=player, json={**NEW, "sportIds": []}).status_code == 422
    assert client.post(f"{API}/communities", headers=player, json={**NEW, "cityCode": "000000000"}).status_code == 422


def test_private_communities_are_only_visible_to_members(client, player):
    secret = client.post(f"{API}/communities", headers=player, json={**NEW, "name": "Invite Only", "visibility": "private"}).json()
    _, stranger = new_user("Stranger")
    assert "Invite Only" not in names(client.get(f"{API}/communities"))
    assert client.get(f"{API}/communities/{secret['id']}", headers=stranger).status_code == 404
    assert client.post(f"{API}/communities/{secret['id']}/join", headers=stranger).status_code == 404
    assert client.get(f"{API}/communities/{secret['id']}", headers=player).status_code == 200
    assert "Invite Only" in names(client.get(f"{API}/communities", params={"mine": True}, headers=player))


def test_sessions_can_be_found_by_community(client):
    rally = next(item for item in client.get(f"{API}/communities").json() if item["name"] == "Rally Community")
    sessions = client.get(f"{API}/sessions", params={"communityId": rally["id"]}).json()
    assert [item["title"] for item in sessions] == ["Saturday Sunrise Rally"]
    assert sessions[0]["community"] == {"id": rally["id"], "name": "Rally Community"}


def test_teams(client, player):
    teams = client.get(f"{API}/teams").json()
    assert {team["name"] for team in teams} == {"Demo Hoopers Blue", "Demo Rally Pair"}
    assert [team["name"] for team in client.get(f"{API}/teams", params={"mine": True}, headers=player).json()] == ["Demo Rally Pair"]
    assert [team["name"] for team in client.get(f"{API}/teams", params={"sportId": "basketball"}).json()] == ["Demo Hoopers Blue"]

    created = client.post(f"{API}/teams", headers=player, json={"name": "Net Gains", "sportId": "volleyball", "cityCode": "137404000"})
    assert created.status_code == 201, created.text
    team = created.json()
    assert team["viewerRole"] == "captain" and team["captain"]["displayName"] == "Demo Player" and team["memberCount"] == 1
    assert client.post(f"{API}/teams", headers=player, json={"name": "Net Gains", "sportId": "volleyball"}).status_code == 409
    assert client.post(f"{API}/teams", headers=player, json={"name": "Net Gains", "sportId": "football"}).status_code == 201

    friend_id, friend = new_user("New Friend")
    assert client.post(f"{API}/teams/{team['id']}/join", headers=friend).json()["memberCount"] == 2
    assert "captain cannot leave" in client.post(f"{API}/teams/{team['id']}/leave", headers=player).json()["detail"]
    assert client.delete(f"{API}/teams/{team['id']}/members/{friend_id}", headers=friend).status_code == 403
    assert client.delete(f"{API}/teams/{team['id']}/members/{friend_id}", headers=player).json()["memberCount"] == 1
    assert client.post(f"{API}/teams/{team['id']}/leave", headers=friend).status_code == 409


def test_team_in_a_community_needs_membership(client, player):
    hoopers = next(item for item in client.get(f"{API}/communities").json() if item["name"] == "Demo Malolos Hoopers")
    payload = {"name": "Hoopers Gold", "sportId": "basketball", "communityId": hoopers["id"]}
    assert client.post(f"{API}/teams", headers=player, json=payload).status_code == 403
    client.post(f"{API}/communities/{hoopers['id']}/join", headers=player)
    assert client.post(f"{API}/teams", headers=player, json=payload).json()["community"]["name"] == "Demo Malolos Hoopers"


def test_joining_a_session_with_a_team_requires_your_own_team(client, player):
    session = next(item for item in client.get(f"{API}/sessions").json() if item["title"] == "Midweek Dink and Drink")
    teams = {team["name"]: team["id"] for team in client.get(f"{API}/teams").json()}
    url = f"{API}/sessions/{session['id']}/join"
    assert client.post(url, headers=player, json={"teamId": teams["Demo Hoopers Blue"]}).status_code == 422
    assert client.post(url, headers=player, json={"teamId": teams["Demo Rally Pair"]}).status_code == 200
