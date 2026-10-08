from app import schemas
from app.sports_catalog import CATEGORIES, SPORTS

from .conftest import API

REQUIRED_SPORTS = {
    "pickleball", "badminton", "tennis", "table_tennis",
    "basketball", "volleyball", "football",
    "baseball", "softball",
    "bowling", "billiards", "darts", "chess", "esports",
    "running", "cycling", "swimming", "martial_arts", "boxing", "muay_thai", "bjj", "taekwondo",
    "dance_fitness", "yoga", "calisthenics", "climbing",
    "golf", "skating", "skateboarding", "beach_volleyball",
}  # fmt: skip

NEW_SPORT = {
    "id": "sepak_takraw",
    "name": "Sepak Takraw",
    "categoryId": "team_court",
    "icon": "🏐",
    "bookingEligible": True,
    "queueEligible": True,
    "resourceTypes": ["court"],
    "playerConfig": {"minPlayers": 6, "maxPlayers": 18, "teamFormats": [{"id": "regu", "label": "Regu 3 v 3", "playersPerSide": 3}]},
    "matchFormat": {"type": "two_sided", "sessionKinds": ["open_play", "tournament"], "queueModes": ["winner_stays"]},
    "scoringConfig": {"kind": "games", "unit": "points", "bestOf": 3, "gameLabel": "Sets"},
}


def test_every_requested_sport_is_in_the_catalog(client):
    sports = client.get(f"{API}/sports").json()
    assert {sport["id"] for sport in sports} == REQUIRED_SPORTS
    assert len(sports) == 30


def test_catalog_definitions_satisfy_the_configuration_schema():
    for definition in SPORTS:
        schemas.PlayerConfig.model_validate(definition["player_config"])
        schemas.MatchFormat.model_validate(definition["match_format"])
        schemas.ScoringConfig.model_validate(definition["scoring_config"])
        if definition["queue_eligible"]:
            assert definition["match_format"]["queueModes"], definition["id"]
        else:
            assert not definition["match_format"]["queueModes"], definition["id"]


def test_six_categories_in_order(client):
    categories = client.get(f"{API}/sports/categories").json()
    assert [item["id"] for item in categories] == [key for key, _ in CATEGORIES]


def test_sports_are_configured_differently(client):
    by_id = {sport["id"]: sport for sport in client.get(f"{API}/sports").json()}
    assert by_id["badminton"]["queueEligible"] and by_id["badminton"]["resourceTypes"] == ["court"]
    assert by_id["bowling"]["resourceTypes"] == ["lane"] and not by_id["bowling"]["queueEligible"]
    assert by_id["swimming"]["resourceTypes"] == ["pool", "pool_lane"]
    assert by_id["running"]["matchFormat"]["usesRoutes"] and not by_id["running"]["bookingEligible"]
    assert by_id["basketball"]["resourceTypes"] == ["court", "half_court"]
    assert {field["key"] for field in by_id["basketball"]["scoringConfig"]["playerFields"]} == {"points", "rebounds", "assists"}
    assert by_id["golf"]["matchFormat"]["sessionKinds"][0] == "tee_time"
    assert by_id["yoga"]["scoringConfig"]["kind"] == "none"


def test_filters(client):
    racket = client.get(f"{API}/sports", params={"category": "racket_paddle"}).json()
    assert [sport["id"] for sport in racket] == ["pickleball", "badminton", "tennis", "table_tennis"]
    queue = {sport["id"] for sport in client.get(f"{API}/sports", params={"queue": True}).json()}
    assert "badminton" in queue and "running" not in queue
    not_bookable = {sport["id"] for sport in client.get(f"{API}/sports", params={"bookable": False}).json()}
    assert not_bookable == {"running", "cycling", "skateboarding"}


def test_unknown_sport_is_404(client):
    assert client.get(f"{API}/sports/quidditch").status_code == 404


def test_admin_can_add_a_sport_without_a_code_change(client, admin):
    created = client.post(f"{API}/admin/sports", headers=admin, json=NEW_SPORT)
    assert created.status_code == 201, created.text
    assert client.get(f"{API}/sports/sepak_takraw").json()["matchFormat"]["queueModes"] == ["winner_stays"]
    assert len(client.get(f"{API}/sports").json()) == 31
    assert client.post(f"{API}/admin/sports", headers=admin, json=NEW_SPORT).status_code == 409


def test_only_admins_manage_the_catalog(client, player):
    assert client.post(f"{API}/admin/sports", json=NEW_SPORT).status_code == 401
    assert client.post(f"{API}/admin/sports", headers=player, json=NEW_SPORT).status_code == 403
    assert client.patch(f"{API}/admin/sports/tennis", headers=player, json={"name": "Lawn Tennis"}).status_code == 403


def test_admin_sport_validation(client, admin):
    bad_category = {**NEW_SPORT, "categoryId": "nope"}
    assert client.post(f"{API}/admin/sports", headers=admin, json=bad_category).status_code == 422
    bad_resource = {**NEW_SPORT, "resourceTypes": ["hoverpad"]}
    assert client.post(f"{API}/admin/sports", headers=admin, json=bad_resource).status_code == 422
    no_queue_mode = {**NEW_SPORT, "matchFormat": {"type": "two_sided", "sessionKinds": ["open_play"]}}
    assert client.post(f"{API}/admin/sports", headers=admin, json=no_queue_mode).status_code == 422
    bad_id = {**NEW_SPORT, "id": "Sepak Takraw!"}
    assert client.post(f"{API}/admin/sports", headers=admin, json=bad_id).status_code == 422
    bad_aggregation = {
        **NEW_SPORT,
        "scoringConfig": {
            "kind": "individual",
            "activityFields": [{"key": "score", "label": "Score"}],
            "aggregations": [{"key": "x", "label": "X", "op": "sum", "field": "missing"}],
        },
    }
    assert client.post(f"{API}/admin/sports", headers=admin, json=bad_aggregation).status_code == 422


def test_admin_can_edit_and_retire_a_sport(client, admin):
    patched = client.patch(
        f"{API}/admin/sports/tennis", headers=admin, json={"description": "Hard and clay courts.", "queueEligible": False}
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Hard and clay courts."
    assert client.patch(f"{API}/admin/sports/darts", headers=admin, json={"isActive": False}).status_code == 200
    assert client.get(f"{API}/sports/darts").status_code == 404
    assert len(client.get(f"{API}/sports").json()) == 29


def test_resource_types_are_listed(client):
    types = {item["id"] for item in client.get(f"{API}/resource-types").json()}
    assert {"court", "field", "lane", "table", "studio", "pool", "training_area", "other"} <= types
