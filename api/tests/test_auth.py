import datetime as dt

from sqlalchemy import select

from app import security
from app.models import AuthToken, User

from .conftest import API

GOOD = {"email": "Ana@Example.com", "password": "correct horse 42", "displayName": "Ana Reyes"}


def register(client, **overrides):
    return client.post(f"{API}/auth/register", json={**GOOD, **overrides})


def test_register_returns_a_token_and_profile(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["user"]["email"] == "ana@example.com"
    assert body["user"]["initials"] == "AR"
    assert body["user"]["role"] == "player"
    assert "password" not in str(body).lower()


def test_passwords_are_stored_as_scrypt_hashes(client, db):
    register(client)
    user = db.scalar(select(User).where(User.email == "ana@example.com"))
    assert user.password_hash.startswith("scrypt$")
    assert GOOD["password"] not in user.password_hash
    assert security.verify_password(GOOD["password"], user.password_hash)
    assert not security.verify_password("wrong password", user.password_hash)


def test_tokens_are_stored_as_digests(client, db):
    token = register(client).json()["accessToken"]
    stored = db.scalars(select(AuthToken.token_hash)).all()
    assert token not in stored
    assert all(len(value) == 64 for value in stored)


def test_duplicate_email_is_rejected(client):
    assert register(client).status_code == 201
    assert register(client, email="ANA@example.com").status_code == 409


def test_weak_password_and_bad_email_are_rejected(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, displayName="A").status_code == 422


def test_login_and_me(client):
    register(client)
    login = client.post(f"{API}/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert client.get(f"{API}/auth/me", headers=headers).json()["displayName"] == "Ana Reyes"


def test_login_failures_do_not_reveal_which_part_was_wrong(client):
    register(client)
    wrong_password = client.post(f"{API}/auth/login", json={"email": GOOD["email"], "password": "definitely wrong"})
    unknown_email = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "definitely wrong"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_me_requires_a_valid_token(client):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_revokes_the_token(client):
    headers = {"Authorization": f"Bearer {register(client).json()['accessToken']}"}
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 204
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_expired_tokens_are_rejected(client, db):
    headers = {"Authorization": f"Bearer {register(client).json()['accessToken']}"}
    token = db.scalar(select(AuthToken))
    token.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.commit()
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_demo_personas(client):
    for persona, role in (("player", "player"), ("operator", "player"), ("admin", "admin")):
        body = client.post(f"{API}/auth/demo", json={"persona": persona}).json()
        assert body["user"]["isDemo"] is True
        assert body["user"]["role"] == role
    operator = client.post(f"{API}/auth/demo", json={"persona": "operator"}).json()["user"]
    assert len(operator["managedFacilityIds"]) == 6


def test_demo_accounts_cannot_use_password_login(client):
    response = client.post(f"{API}/auth/login", json={"email": "demo.player@courtmate.demo", "password": "anything at all"})
    assert response.status_code == 401


def test_demo_login_can_be_switched_off(client, monkeypatch):
    from app.config import Settings
    from app.routers import auth

    monkeypatch.setattr(auth, "get_settings", lambda: Settings(demo_login=False))
    assert client.post(f"{API}/auth/demo", json={"persona": "player"}).status_code == 404


def test_profile_update(client, player):
    response = client.patch(
        f"{API}/auth/me",
        headers=player,
        json={
            "displayName": "Demo Baller",
            "bio": "Weekend hooper",
            "cityCode": "031410000",
            "sports": [{"sportId": "basketball", "skillLevel": "Intermediate", "isPrimary": True}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["displayName"] == "Demo Baller"
    assert body["city"]["name"] == "City of Malolos"
    assert body["sports"] == [{"sportId": "basketball", "skillLevel": "Intermediate", "isPrimary": True}]


def test_profile_update_rejects_unknown_references(client, player):
    assert client.patch(f"{API}/auth/me", headers=player, json={"cityCode": "000000000"}).status_code == 422
    assert client.patch(f"{API}/auth/me", headers=player, json={"sports": [{"sportId": "quidditch"}]}).status_code == 422


def test_login_is_rate_limited(client):
    register(client)
    statuses = [
        client.post(f"{API}/auth/login", json={"email": GOOD["email"], "password": "wrong password"}).status_code for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
